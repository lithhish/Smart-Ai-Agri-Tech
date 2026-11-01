
import os
import math
import json
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from io import StringIO

import pandas as pd
import requests
from flask import Flask, render_template, jsonify, request, send_from_directory, Response
import esp32_line_fault
import agriculture_tasks
import agriculture_schemes_market
import agriculture_docs


app = Flask(__name__)

# Set these environment variables to your farm's coordinates (default: original plot place 11.27°N, 77.61°E).
FARM_LAT = os.getenv("FARM_LAT", "11.27")
FARM_LON = os.getenv("FARM_LON", "77.61")

def interpret_weather_code(code, precip=0.0):
    """Interpret WMO weather code into condition category (Normal, Sunny, Rainy, etc.)."""
    if code is None:
        if precip and precip > 0:
            return {"condition": "Rainy", "icon": "🌧️", "text": "🌧️ Rainy"}
        return {"condition": "Normal", "icon": "☀️", "text": "☀️ Normal / Clear"}

    if code == 0:
        return {"condition": "Sunny", "icon": "☀️", "text": "☀️ Sunny"}
    elif code in (1, 2):
        return {"condition": "Normal", "icon": "🌤️", "text": "🌤️ Normal / Partly Cloudy"}
    elif code == 3:
        return {"condition": "Normal", "icon": "☁️", "text": "☁️ Normal / Overcast"}
    elif code in (45, 48):
        return {"condition": "Foggy", "icon": "🌫️", "text": "🌫️ Foggy"}
    elif code in (51, 53, 55):
        return {"condition": "Rainy", "icon": "🌦️", "text": "🌦️ Light Drizzle / Rainy"}
    elif code in (56, 57, 66, 67):
        return {"condition": "Rainy", "icon": "🌧️", "text": "🌧️ Freezing Rain"}
    elif code in (61, 63, 65):
        return {"condition": "Rainy", "icon": "🌧️", "text": "🌧️ Rainy"}
    elif code in (71, 73, 75, 77, 85, 86):
        return {"condition": "Snowy", "icon": "❄️", "text": "❄️ Snowy"}
    elif code in (80, 81, 82):
        return {"condition": "Rainy", "icon": "🌧️", "text": "🌧️ Rain Showers"}
    elif code in (95, 96, 99):
        return {"condition": "Thunderstorm", "icon": "⛈️", "text": "⛈️ Thunderstorm"}
    return {"condition": "Normal", "icon": "🌤️", "text": "🌤️ Normal"}

DB_PATH = "farm_data.db"

NOAA_URL = (
    "https://www.cpc.ncep.noaa.gov/"
    "products/analysis_monitoring/enso/oni/v6/index.php"
)

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

CACHE_SECONDS = 24 * 60 * 60
WEATHER_CACHE_SECONDS = 10 * 60

lock = threading.Lock()
enso_cache = {"checked": None, "data": None}
weather_cache = {"checked": None, "data": None}


def now_utc():
    return datetime.now(timezone.utc)


def timestamp():
    return now_utc().isoformat(timespec="seconds")


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                root_zone_moisture_pct REAL,
                farm_air_temp_c REAL,
                farm_air_humidity_pct REAL,
                soil_temp_c REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pump_control (
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'OFF',
                mode TEXT NOT NULL DEFAULT 'manual',
                flow_rate_lpm REAL DEFAULT 0.0,
                updated_at TEXT NOT NULL,
                last_turned_on TEXT,
                last_turned_off TEXT,
                target_plot TEXT DEFAULT 'Plot B'
            )
        """)
        try:
            conn.execute("ALTER TABLE pump_control ADD COLUMN target_plot TEXT DEFAULT 'Plot B'")
        except Exception:
            pass

        # Ensure single row for pump state exists
        p_row = conn.execute("SELECT id FROM pump_control WHERE id = 1").fetchone()
        if not p_row:
            conn.execute("""
                INSERT INTO pump_control (id, status, mode, flow_rate_lpm, updated_at, last_turned_off, target_plot)
                VALUES (1, 'OFF', 'manual', 0.0, ?, ?, 'Plot B')
            """, (timestamp(), timestamp()))

        conn.execute("""
            CREATE TABLE IF NOT EXISTS farm_health_metrics (
                id INTEGER PRIMARY KEY,
                recorded_at TEXT NOT NULL,
                water_level_pct REAL DEFAULT 78.0,
                water_tank_capacity_l REAL DEFAULT 5000.0,
                water_current_volume_l REAL DEFAULT 3900.0,
                water_inflow_lpm REAL DEFAULT 12.0,
                soil_health_score REAL DEFAULT 88.0,
                soil_ph REAL DEFAULT 6.8,
                soil_organic_carbon_pct REAL DEFAULT 0.72,
                soil_nitrogen_kgha REAL DEFAULT 280.0,
                soil_phosphorus_kgha REAL DEFAULT 45.0,
                soil_potassium_kgha REAL DEFAULT 190.0,
                water_health_score REAL DEFAULT 94.0,
                water_ph REAL DEFAULT 7.2,
                water_tds_ppm REAL DEFAULT 320.0,
                water_ec_dsm REAL DEFAULT 0.62
            )
        """)
        # Ensure single row for health metrics exists
        h_row = conn.execute("SELECT id FROM farm_health_metrics WHERE id = 1").fetchone()
        if not h_row:
            conn.execute("""
                INSERT INTO farm_health_metrics (
                    id, recorded_at, water_level_pct, water_tank_capacity_l, water_current_volume_l, water_inflow_lpm,
                    soil_health_score, soil_ph, soil_organic_carbon_pct, soil_nitrogen_kgha, soil_phosphorus_kgha, soil_potassium_kgha,
                    water_health_score, water_ph, water_tds_ppm, water_ec_dsm
                ) VALUES (
                    1, ?, 78.0, 5000.0, 3900.0, 12.0,
                    88.0, 6.8, 0.72, 280.0, 45.0, 190.0,
                    94.0, 7.2, 320.0, 0.62
                )
            """, (timestamp(),))

    try:
        import agriculture_docs
        agriculture_docs.init_docs_db()
        import esp32_line_fault
        esp32_line_fault.init_line_fault_db()
        import agriculture_tasks
        agriculture_tasks.init_tasks_db()
    except Exception as e:
        print(f"[Init DB] Docs/Tasks init error: {e}")


def get_enso(force=False):
    """Retrieve the latest available ONI table from NOAA."""
    with lock:
        checked = enso_cache["checked"]

        if (
            not force
            and checked
            and (now_utc() - checked).total_seconds() < CACHE_SECONDS
        ):
            return enso_cache["data"]

        try:
            response = requests.get(
                NOAA_URL,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            response.raise_for_status()

            tables = pd.read_html(StringIO(response.text))
            seasons = [
                "DJF", "JFM", "FMA", "MAM",
                "AMJ", "MJJ", "JJA", "JAS",
                "ASO", "SON", "OND", "NDJ"
            ]

            result = None

            for df in tables:
                if len(df) > 0 and any(str(val).strip().lower() == "year" for val in df.iloc[0]):
                    df.columns = df.iloc[0]
                    df = df.iloc[1:]

                # NOAA tables may have multi-row headers.
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [
                        " ".join(str(x) for x in col
                                 if str(x) != "nan").strip()
                        for col in df.columns
                    ]

                df.columns = [
                    str(c).strip() for c in df.columns
                ]

                year_col = next(
                    (c for c in df.columns
                     if str(c).lower() == "year"),
                    None
                )
                if year_col is None:
                    continue

                available = [
                    s for s in seasons if s in df.columns
                ]
                if not available:
                    continue

                df[year_col] = pd.to_numeric(
                    df[year_col], errors="coerce"
                )
                df = df.dropna(subset=[year_col]).copy()
                df = df.sort_values(year_col, ascending=False)

                for _, row in df.iterrows():
                    for season in reversed(available):
                        value = pd.to_numeric(
                            row[season], errors="coerce"
                        )
                        if pd.notna(value):
                            oni = float(value)

                            if oni >= 0.5:
                                phase = "El Niño"
                            elif oni <= -0.5:
                                phase = "La Niña"
                            else:
                                phase = "Neutral"

                            result = {
                                "value": oni,
                                "value_c": oni,
                                "period": (
                                    f"{season} "
                                    f"{int(row[year_col])}"
                                ),
                                "phase": phase,
                                "source": "NOAA CPC",
                                "source_url": NOAA_URL,
                                "checked_at": timestamp()
                            }
                            break

                    if result:
                        break

                if result:
                    break

            if not result:
                raise ValueError(
                    "Could not identify the ONI table. "
                    "NOAA's page format may have changed."
                )

            enso_cache["data"] = result
            enso_cache["checked"] = now_utc()
            return result

        except Exception as exc:
            # Keep the last successful reading, if there is one.
            if enso_cache["data"]:
                stale = dict(enso_cache["data"])
                stale["warning"] = str(exc)
                stale["stale"] = True
                return stale

            return {
                "error": str(exc),
                "source_url": NOAA_URL
            }


def get_weather(force=False, lat=None, lon=None):
    """Retrieve current local outdoor weather from Open-Meteo."""
    target_lat = str(lat or FARM_LAT).strip()
    target_lon = str(lon or FARM_LON).strip()

    with lock:
        checked = weather_cache["checked"]
        cached_lat = weather_cache.get("lat")
        cached_lon = weather_cache.get("lon")

        if (
            not force
            and checked
            and cached_lat == target_lat
            and cached_lon == target_lon
            and (now_utc() - checked).total_seconds()
            < WEATHER_CACHE_SECONDS
        ):
            return weather_cache["data"]

        if not target_lat or not target_lon:
            return {
                "error": (
                    "Set FARM_LAT and FARM_LON to your farm "
                    "coordinates before requesting weather."
                )
            }

        try:
            response = requests.get(
                WEATHER_URL,
                params={
                    "latitude": target_lat,
                    "longitude": target_lon,
                    "current": (
                        "temperature_2m,relative_humidity_2m,"
                        "apparent_temperature,precipitation,"
                        "weather_code,wind_speed_10m,is_day"
                    ),
                    "timezone": "auto"
                },
                timeout=15
            )
            response.raise_for_status()
            payload = response.json()
            current = payload.get("current")

            if not current:
                raise ValueError("Weather API returned no current data.")

            code = current.get("weather_code")
            precip = current.get("precipitation", 0.0)
            cond = interpret_weather_code(code, precip)

            # Determine human-friendly locality name
            try:
                lat_f = float(target_lat)
                lon_f = float(target_lon)
                loc_name = f"{lat_f:.2f}°N, {lon_f:.2f}°E"
            except Exception:
                loc_name = "11.27°N, 77.61°E"

            result = {
                "temperature_c": current.get("temperature_2m"),
                "apparent_temperature_c": current.get("apparent_temperature"),
                "humidity_pct": current.get("relative_humidity_2m"),
                "precipitation_mm": precip,
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "is_day": current.get("is_day", 1),
                "weather_code": code,
                "condition": cond["condition"],
                "condition_text": cond["text"],
                "condition_icon": cond["icon"],
                "location_name": loc_name,
                "latitude": target_lat,
                "longitude": target_lon,
                "observed_at": current.get("time"),
                "source": "Open-Meteo",
                "checked_at": timestamp()
            }
            # Add field aliases for frontend compatibility
            result["temperature"] = result["temperature_c"]
            result["apparent_temperature"] = result["apparent_temperature_c"]
            result["humidity"] = result["humidity_pct"]
            result["wind_speed"] = result["wind_speed_kmh"]
            result["precipitation"] = result["precipitation_mm"]
            result["loc_name"] = result["location_name"]

            weather_cache["data"] = result
            weather_cache["checked"] = now_utc()
            weather_cache["lat"] = target_lat
            weather_cache["lon"] = target_lon
            return result

        except Exception as exc:
            if weather_cache["data"]:
                stale = dict(weather_cache["data"])
                stale["warning"] = str(exc)
                stale["stale"] = True
                return stale

            return {"error": str(exc)}


def latest_sensor_reading():
    with connect_db() as conn:
        row = conn.execute("""
            SELECT * FROM sensor_readings
            ORDER BY id DESC LIMIT 1
        """).fetchone()

    if row is None:
        return None

    result = dict(row)
    result["soil_moisture"] = result.get("root_zone_moisture_pct")
    result["temperature"] = result.get("farm_air_temp_c")
    result["humidity"] = result.get("farm_air_humidity_pct")
    result["soil_temperature"] = result.get("soil_temp_c")
    result["age_seconds"] = max(
        0,
        int(
            (now_utc() - datetime.fromisoformat(
                result["received_at"]
            )).total_seconds()
        )
    )
    return result


FARM_PLOTS = {
    "Plot A": {
        "id": "plot_a",
        "name": "Plot A",
        "crop": "Sugarcane (Co 0238)",
        "area_acres": 2.5,
        "soil_type": "Red Loam (Perur, Coimbatore)",
        "moisture_pct": 42.5,
        "soil_temp_c": 21.2,
        "water_level_pct": 78.0,
        "water_volume_l": 3900.0,
        "water_capacity_l": 5000.0,
        "water_status": "Normal Reserve",
        "water_inflow_lpm": 12.0,
        "water_head_m": 32,
        "soil_health_score": 88.0,
        "soil_grade": "Optimal • Grade A",
        "soil_ph": 6.8,
        "organic_carbon_pct": 0.72,
        "npk": "280-45-190 kg/ha",
        "npk_balance": "Well Balanced",
        "irrigation_status": "Adequate (No Pumping Needed)",
        "valve_status": "Valve Standby"
    },
    "Plot B": {
        "id": "plot_b",
        "name": "Plot B",
        "crop": "Bt Cotton & Hybrid Maize",
        "area_acres": 1.8,
        "soil_type": "Black Cotton Soil",
        "moisture_pct": 34.8,
        "soil_temp_c": 23.4,
        "water_level_pct": 64.0,
        "water_volume_l": 3200.0,
        "water_capacity_l": 5000.0,
        "water_status": "Adequate Reserve",
        "water_inflow_lpm": 10.5,
        "water_head_m": 28,
        "soil_health_score": 79.0,
        "soil_grade": "Good • Grade B+",
        "soil_ph": 7.1,
        "organic_carbon_pct": 0.65,
        "npk": "240-38-160 kg/ha",
        "npk_balance": "Moderate Nitrogen",
        "irrigation_status": "Irrigation Recommended (< 40%)",
        "valve_status": "Ready for Drip"
    },
    "Plot C": {
        "id": "plot_c",
        "name": "Plot C",
        "crop": "Banana & Salem Turmeric",
        "area_acres": 1.2,
        "soil_type": "Alluvial Red Soil",
        "moisture_pct": 49.0,
        "soil_temp_c": 20.8,
        "water_level_pct": 82.0,
        "water_volume_l": 4100.0,
        "water_capacity_l": 5000.0,
        "water_status": "High Reserve",
        "water_inflow_lpm": 14.0,
        "water_head_m": 35,
        "soil_health_score": 92.0,
        "soil_grade": "Optimal • Grade A+",
        "soil_ph": 6.6,
        "organic_carbon_pct": 0.85,
        "npk": "310-52-210 kg/ha",
        "npk_balance": "Rich Organic Matrix",
        "irrigation_status": "Adequate Reserve",
        "valve_status": "Standby"
    },
    "Plot D": {
        "id": "plot_d",
        "name": "Plot D",
        "crop": "Coconut & Teak Agroforestry",
        "area_acres": 3.0,
        "soil_type": "Sandy Clay Loam",
        "moisture_pct": 45.2,
        "soil_temp_c": 22.1,
        "water_level_pct": 75.0,
        "water_volume_l": 3750.0,
        "water_capacity_l": 5000.0,
        "water_status": "Normal Reserve",
        "water_inflow_lpm": 11.0,
        "water_head_m": 30,
        "soil_health_score": 85.0,
        "soil_grade": "Optimal • Grade A",
        "soil_ph": 6.9,
        "organic_carbon_pct": 0.76,
        "npk": "260-40-175 kg/ha",
        "npk_balance": "Stable Humus",
        "irrigation_status": "Adequate Reserve",
        "valve_status": "Standby"
    }
}


def get_pump_status():
    """Retrieve the current pump state, operating mode, target plot, and live flow rate."""
    try:
        with connect_db() as conn:
            row = conn.execute("SELECT * FROM pump_control WHERE id = 1").fetchone()
            if row:
                d = dict(row)
                runtime_mins = 0
                if d.get("status") == "ON" and d.get("last_turned_on"):
                    try:
                        on_time = datetime.fromisoformat(d["last_turned_on"])
                        runtime_mins = max(1, int((now_utc() - on_time).total_seconds() / 60))
                    except Exception:
                        runtime_mins = 1
                d["runtime_mins"] = runtime_mins
                d.setdefault("target_plot", "Plot B")
                return d
    except Exception as e:
        print(f"[Pump] Status read error: {e}")

    return {
        "id": 1,
        "status": "OFF",
        "mode": "manual",
        "flow_rate_lpm": 0.0,
        "updated_at": timestamp(),
        "runtime_mins": 0,
        "target_plot": "Plot B"
    }


def toggle_pump(target_status=None, mode=None, target_plot=None):
    """Toggle or set irrigation pump status (ON/OFF), mode, and target plot."""
    try:
        with connect_db() as conn:
            current = get_pump_status()
            if target_status in ("ON", "OFF"):
                new_status = target_status
            else:
                new_status = "OFF" if current.get("status") == "ON" else "ON"

            new_mode = mode if mode in ("manual", "auto") else current.get("mode", "manual")
            new_plot = target_plot or current.get("target_plot", "Plot B")
            flow = 42.5 if new_status == "ON" else 0.0
            now_ts = timestamp()

            last_on = now_ts if new_status == "ON" else current.get("last_turned_on")
            last_off = now_ts if new_status == "OFF" else current.get("last_turned_off")

            conn.execute("""
                UPDATE pump_control
                SET status = ?, mode = ?, flow_rate_lpm = ?, updated_at = ?, last_turned_on = ?, last_turned_off = ?, target_plot = ?
                WHERE id = 1
            """, (new_status, new_mode, flow, now_ts, last_on, last_off, new_plot))
    except Exception as e:
        print(f"[Pump] Toggle error: {e}")

    return get_pump_status()


def get_farm_health_metrics():
    """Retrieve water reservoir level, soil health metrics, and water health quality indices."""
    try:
        with connect_db() as conn:
            row = conn.execute("SELECT * FROM farm_health_metrics WHERE id = 1").fetchone()
            if row:
                return dict(row)
    except Exception as e:
        print(f"[Health Metrics] Read error: {e}")

    return {
        "water_level_pct": 78.0,
        "water_tank_capacity_l": 5000.0,
        "water_current_volume_l": 3900.0,
        "water_inflow_lpm": 12.0,
        "soil_health_score": 88.0,
        "soil_ph": 6.8,
        "soil_organic_carbon_pct": 0.72,
        "soil_nitrogen_kgha": 280.0,
        "soil_phosphorus_kgha": 45.0,
        "soil_potassium_kgha": 190.0,
        "water_health_score": 94.0,
        "water_ph": 7.2,
        "water_tds_ppm": 320.0,
        "water_ec_dsm": 0.62
    }


ROVER_WAYPOINTS = {
    "Plot A": {"lat": 11.2712, "lon": 77.6086, "name": "Plot A", "crop": "Sugarcane (2.5 ac)"},
    "Plot B": {"lat": 11.2714, "lon": 77.6118, "name": "Plot B", "crop": "Bt Cotton & Hybrid Maize (1.8 ac)"},
    "Plot C": {"lat": 11.2684, "lon": 77.6085, "name": "Plot C", "crop": "Banana (1.2 ac)"},
    "Plot D": {"lat": 11.2685, "lon": 77.6119, "name": "Plot D", "crop": "Orchard (3.0 ac)"},
    "Dock": {"lat": 11.2699, "lon": 77.6100, "name": "Base Dock", "crop": "Solar Charging Station"}
}

rover_state = {
    "rover_id": "AgriBot-Rover 1",
    "status": "SURVEYING",
    "mode": "autonomous",
    "current_plot": "Plot B",
    "lat": 11.2714,
    "lon": 77.6118,
    "heading_deg": 45,
    "speed_mps": 1.2,
    "battery_pct": 94,
    "soil_probe_depth_cm": 15,
    "soil_probe_status": "deployed",
    "soil_moisture_pct": 34.8,
    "soil_temp_c": 23.4,
    "farm_air_temp_c": 25.1,
    "canopy_humidity_pct": 77,
    "lora_rssi_dbm": -68,
    "obstacle_clearance_m": 4.5,
    "last_sampled": timestamp(),
    "trail": [
        {"lat": 11.2700, "lon": 77.6100, "ts": "Base Dock"},
        {"lat": 11.2707, "lon": 77.6108, "ts": "Transit Waypoint"},
        {"lat": 11.2714, "lon": 77.6118, "ts": "Plot B Sensing Point"}
    ]
}


def get_rover_status():
    """Return the current autonomous rover telemetry and location."""
    with lock:
        p_data = FARM_PLOTS.get(rover_state.get("current_plot", "Plot B"), {})
        if p_data:
            rover_state["soil_moisture_pct"] = p_data.get("moisture_pct", rover_state["soil_moisture_pct"])
            rover_state["soil_temp_c"] = p_data.get("soil_temp_c", rover_state["soil_temp_c"])
        return dict(rover_state)


def control_rover(command, params=None):
    """Execute motion command, tool trigger, or mode change on the rover."""
    params = params or {}
    with lock:
        cmd = str(command).lower()
        if (cmd in ("goto", "navigate_coords", "move_to") or (params and "lat" in params and "lon" in params)):
            target_lat = float(params["lat"])
            target_lon = float(params["lon"])
            d_lat = target_lat - rover_state["lat"]
            d_lon = target_lon - rover_state["lon"]
            angle_rad = math.atan2(d_lon, d_lat)
            angle_deg = int(math.degrees(angle_rad)) % 360
            rover_state["lat"] = round(target_lat, 5)
            rover_state["lon"] = round(target_lon, 5)
            rover_state["heading_deg"] = angle_deg
            rover_state["status"] = "DISPATCHED"
            rover_state["speed_mps"] = 1.4
            for pname, pdata in FARM_PLOTS.items():
                p_coords = pdata.get("coordinates", {})
                if abs(p_coords.get("lat", 0) - target_lat) < 0.0020 and abs(p_coords.get("lon", 0) - target_lon) < 0.0020:
                    rover_state["current_plot"] = pname
                    break
            rover_state["trail"].append({"lat": rover_state["lat"], "lon": rover_state["lon"], "ts": f"Cursor Target ({rover_state['current_plot']})"})
        elif cmd == "forward":
            rad = math.radians(rover_state["heading_deg"])
            rover_state["lat"] = round(rover_state["lat"] + 0.00035 * math.cos(rad), 5)
            rover_state["lon"] = round(rover_state["lon"] + 0.00035 * math.sin(rad), 5)
            rover_state["status"] = "DRIVING"
            rover_state["speed_mps"] = 1.2
            rover_state["trail"].append({"lat": rover_state["lat"], "lon": rover_state["lon"], "ts": "Forward Steer"})
        elif cmd == "reverse":
            rad = math.radians(rover_state["heading_deg"])
            rover_state["lat"] = round(rover_state["lat"] - 0.00035 * math.cos(rad), 5)
            rover_state["lon"] = round(rover_state["lon"] - 0.00035 * math.sin(rad), 5)
            rover_state["status"] = "REVERSING"
            rover_state["speed_mps"] = 0.8
            rover_state["trail"].append({"lat": rover_state["lat"], "lon": rover_state["lon"], "ts": "Reverse Steer"})
        elif cmd == "left":
            rover_state["heading_deg"] = (rover_state["heading_deg"] - 30) % 360
            rover_state["status"] = "TURNING"
        elif cmd == "right":
            rover_state["heading_deg"] = (rover_state["heading_deg"] + 30) % 360
            rover_state["status"] = "TURNING"
        elif cmd in ("stop", "halt"):
            rover_state["status"] = "STANDBY"
            rover_state["speed_mps"] = 0.0
        elif cmd == "emergency_stop":
            rover_state["status"] = "EMERGENCY_STOP"
            rover_state["speed_mps"] = 0.0
            rover_state["soil_probe_status"] = "retracted"
        elif cmd == "sample_probe":
            rover_state["status"] = "SAMPLING"
            rover_state["soil_probe_status"] = "deployed"
            rover_state["soil_probe_depth_cm"] = 15
            rover_state["last_sampled"] = timestamp()
        elif cmd == "auto_survey":
            rover_state["mode"] = "autonomous"
            rover_state["status"] = "SURVEYING"
            rover_state["speed_mps"] = 1.0

        if len(rover_state["trail"]) > 25:
            rover_state["trail"] = rover_state["trail"][-25:]

        return dict(rover_state)


def navigate_rover(target):
    """Navigate the rover to a specific plot or waypoint."""
    with lock:
        plot_key = target if target in ROVER_WAYPOINTS else "Plot B"
        wp = ROVER_WAYPOINTS.get(plot_key, ROVER_WAYPOINTS["Plot B"])
        rover_state["current_plot"] = plot_key if plot_key != "Dock" else "Dock"
        rover_state["lat"] = wp["lat"]
        rover_state["lon"] = wp["lon"]
        rover_state["status"] = "SURVEYING" if plot_key != "Dock" else "DOCKED"
        rover_state["speed_mps"] = 1.2 if plot_key != "Dock" else 0.0
        p_data = FARM_PLOTS.get(plot_key, {})
        if p_data:
            rover_state["soil_moisture_pct"] = p_data.get("moisture_pct", 34.8)
            rover_state["soil_temp_c"] = p_data.get("soil_temp_c", 23.4)
        rover_state["trail"].append({"lat": wp["lat"], "lon": wp["lon"], "ts": f"{plot_key} Dispatched"})
        if len(rover_state["trail"]) > 25:
            rover_state["trail"] = rover_state["trail"][-25:]
        return dict(rover_state)


@app.route("/")
def dashboard():
    return render_template("index.html")

@app.route("/rover")
def rover_mission_page():
    """Dedicated page for Field Rover GIS Map and Mission Control."""
    return render_template("rover.html")

@app.route("/disease-prediction")
def disease_prediction_page():
    """Dedicated page for Plant and Crop Disease Prediction Studio."""
    return render_template("disease_prediction.html")

@app.route("/trends-forecasts")
def trends_forecasts_page():
    """Dedicated page for Farm Trends, Disease Risks and Mandi Benchmarks."""
    return render_template("trends_forecasts.html")

@app.route("/farm-records")
def farm_records_page():
    """Dedicated page for Farm Land Document Vault, Records and Subsidies."""
    return render_template("farm_records.html")

@app.route("/daily-tasks")
def daily_tasks_page():
    """Dedicated page for Daily Farm Tasks, Revenue & Benefit Tracking."""
    return render_template("daily_tasks.html")

@app.route("/market-prices")
def market_prices_page():
    """Dedicated page for All-District Live APMC Mandi & Uzhavar Sandhai Prices."""
    return render_template("market_prices.html")

@app.route("/line-fault")
def line_fault_page():
    """Dedicated page for ESP32 Electrical Line Fault & Pole Monitoring System."""
    return render_template("line_fault.html")


@app.route("/api/dashboard")
def dashboard_data():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    force = request.args.get("force", "false").lower() in ("true", "1")
    pump = get_pump_status()
    return jsonify({
        "enso": get_enso(),
        "weather": get_weather(force=force, lat=lat, lon=lon),
        "sensor": latest_sensor_reading(),
        "pump": pump,
        "farm_health": get_farm_health_metrics(),
        "plots": FARM_PLOTS,
        "active_plot": pump.get("target_plot", "Plot B"),
        "rover": get_rover_status(),
        "server_time": timestamp()
    })


@app.route("/api/plots", methods=["GET"])
def plots_endpoint():
    return jsonify({"success": True, "plots": FARM_PLOTS})


@app.route("/api/pump/status", methods=["GET"])
def pump_status_endpoint():
    return jsonify({"success": True, "pump": get_pump_status()})


@app.route("/api/pump/toggle", methods=["POST"])
def pump_toggle_endpoint():
    data = request.get_json(silent=True) or {}
    target_status = data.get("status")
    mode = data.get("mode")
    target_plot = data.get("target_plot") or data.get("plot")
    updated = toggle_pump(target_status=target_status, mode=mode, target_plot=target_plot)
    return jsonify({"success": True, "pump": updated})


@app.route("/api/farm-health", methods=["GET"])
def farm_health_endpoint():
    return jsonify({"success": True, "health": get_farm_health_metrics(), "plots": FARM_PLOTS})


@app.route("/api/rover/status", methods=["GET"])
def rover_status_endpoint():
    return jsonify({"success": True, "rover": get_rover_status(), "waypoints": ROVER_WAYPOINTS})


@app.route("/api/rover/navigate", methods=["POST"])
def rover_navigate_endpoint():
    data = request.get_json(silent=True) or {}
    target = data.get("target_plot") or data.get("target") or data.get("plot") or "Plot B"
    rover = navigate_rover(target)
    return jsonify({"success": True, "rover": rover})


@app.route("/api/rover/control", methods=["POST"])
def rover_control_endpoint():
    data = request.get_json(silent=True) or {}
    command = data.get("command") or data.get("action") or "stop"
    params = data.get("params") or {}
    rover = control_rover(command, params)
    return jsonify({"success": True, "rover": rover})


@app.route("/api/enso/refresh", methods=["POST"])
def refresh_enso():
    return jsonify(get_enso(force=True))


@app.route("/api/weather/refresh", methods=["POST"])
def refresh_weather():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    return jsonify(get_weather(force=True, lat=lat, lon=lon))


@app.route("/api/sensor", methods=["POST"])
def receive_sensor():
    """
    The LoRa receiver sends a JSON POST request here.
    Accept only actual readings received from your hardware.
    """
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object."}), 400

    fields = [
        "root_zone_moisture_pct",
        "farm_air_temp_c",
        "farm_air_humidity_pct",
        "soil_temp_c"
    ]

    cleaned = {}

    for field in fields:
        value = data.get(field)

        if value is None:
            cleaned[field] = None
            continue

        try:
            value = float(value)
        except (TypeError, ValueError):
            return jsonify({
                "error": f"{field} must be a number or null."
            }), 400

        if not pd.notna(value):
            return jsonify({
                "error": f"{field} must be finite."
            }), 400

        if field in (
            "root_zone_moisture_pct",
            "farm_air_humidity_pct"
        ) and not 0 <= value <= 100:
            return jsonify({
                "error": f"{field} must be between 0 and 100."
            }), 400

        cleaned[field] = value

    if all(cleaned[field] is None for field in fields):
        return jsonify({
            "error": "At least one actual sensor reading is required."
        }), 400

    with connect_db() as conn:
        conn.execute("""
            INSERT INTO sensor_readings (
                received_at,
                root_zone_moisture_pct,
                farm_air_temp_c,
                farm_air_humidity_pct,
                soil_temp_c
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            timestamp(),
            cleaned["root_zone_moisture_pct"],
            cleaned["farm_air_temp_c"],
            cleaned["farm_air_humidity_pct"],
            cleaned["soil_temp_c"]
        ))

    return jsonify({
        "status": "saved",
        "received_at": timestamp()
    }), 201


# -------------------------------------------------------------
# Agriculture AI Chatbot & RAG Endpoints
# -------------------------------------------------------------
from agriculture_chatbot import (
    handle_chat_message,
    check_gemini_status,
    SUPPORTED_LANGUAGES
)
from agriculture_rag import rag_system


@app.route("/api/chatbot/status")
def chatbot_status():
    """Return status of Gemini API, active knowledge documents, and supported languages."""
    gemini_info = check_gemini_status()
    sources = rag_system.get_indexed_sources_summary()
    return jsonify({
        "gemini": gemini_info,
        "indexed_sources": sources,
        "total_chunks": len(rag_system.chunks),
        "supported_languages": SUPPORTED_LANGUAGES
    })


@app.route("/api/chatbot/message", methods=["POST"])
def chatbot_message():
    """Handle incoming questions from the user via the frontend chatbot interface."""
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    session_id = data.get("session_id", "default_session")
    requested_lang = data.get("language", "en")

    if not message:
        return jsonify({"error": "Empty message."}), 400

    result = handle_chat_message(
        user_query=message,
        session_id=session_id,
        requested_lang=requested_lang
    )
    return jsonify(result)


@app.route("/api/chatbot/reload_knowledge", methods=["POST"])
def reload_knowledge():
    """Re-scan the agriculture_knowledge/ directory and refresh the vector index."""
    rag_system.load_and_index()
    return jsonify({
        "status": "reindexed",
        "total_chunks": len(rag_system.chunks),
        "sources": rag_system.get_indexed_sources_summary()
    })


# -------------------------------------------------------------
# Crop Disease Prediction & Agricultural Trends Endpoints
# -------------------------------------------------------------
from agriculture_disease import predict_plant_disease, parse_data_url


@app.route("/api/disease/predict", methods=["POST"])
def disease_predict_endpoint():
    """Diagnose crop, leaf, fruit, or vegetable disease from image upload or live camera snapshot."""
    image_bytes = None
    filename = "specimen.jpg"
    language = request.form.get("language") or "en"

    # 1. File Upload
    if "file" in request.files and request.files["file"].filename:
        uploaded_file = request.files["file"]
        filename = uploaded_file.filename
        image_bytes = uploaded_file.read()
    elif "image" in request.files and request.files["image"].filename:
        uploaded_file = request.files["image"]
        filename = uploaded_file.filename
        image_bytes = uploaded_file.read()
    else:
        # 2. JSON or Form Data URL (from live webcam snapshot)
        json_data = request.get_json(silent=True) or {}
        data_url = (
            json_data.get("image")
            or json_data.get("image_base64")
            or json_data.get("data_url")
            or request.form.get("image")
            or request.form.get("image_base64")
        )
        filename = json_data.get("filename") or request.form.get("filename") or "camera_snapshot.jpg"
        language = json_data.get("language") or language

        if data_url:
            try:
                image_bytes = parse_data_url(data_url)
            except Exception as e:
                return jsonify({"success": False, "error": f"Invalid base64 image data: {e}"}), 400

    if not image_bytes:
        return jsonify({"success": False, "error": "No image provided. Please upload an image or capture a camera photo."}), 400

    result = predict_plant_disease(image_bytes, filename=filename, language=language)
    return jsonify(result)


from agriculture_trends import get_annual_analytics_data


@app.route("/api/trends")
def trends_endpoint():
    """Provide historical & forecast agricultural trends (multi-day weather, disease risk, market prices, and annual multi-dimensional analytics)."""
    weather_history = []
    try:
        res = requests.get(
            WEATHER_URL,
            params={
                "latitude": FARM_LAT,
                "longitude": FARM_LON,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
                "past_days": 3,
                "forecast_days": 4,
                "timezone": "auto"
            },
            timeout=8
        )
        if res.status_code == 200:
            d = res.json().get("daily", {})
            times = d.get("time", [])
            max_t = d.get("temperature_2m_max", [])
            min_t = d.get("temperature_2m_min", [])
            precip = d.get("precipitation_sum", [])
            precip_prob = d.get("precipitation_probability_max", [])
            for i in range(len(times)):
                weather_history.append({
                    "date": times[i],
                    "max_temp": max_t[i] if i < len(max_t) else None,
                    "min_temp": min_t[i] if i < len(min_t) else None,
                    "precip_mm": precip[i] if i < len(precip) else 0.0,
                    "rain_prob_pct": precip_prob[i] if i < len(precip_prob) else 0
                })
    except Exception as e:
        print(f"[Trends] Weather trend fetch error: {e}")

    current_weather = get_weather()
    cur_temp = current_weather.get("temperature_c") or 24.0
    cur_humid = current_weather.get("humidity_pct") or 70.0
    cur_precip = current_weather.get("precipitation_mm") or 0.0

    if cur_humid >= 85 and 20 <= cur_temp <= 32:
        fungal_risk = "High"
        fungal_score = 88
        risk_advisory = "High atmospheric humidity (>85%) and warm temperatures favor rapid fungal sporulation (Alternaria blight, Downy Mildew, Rust). Avoid evening irrigation."
    elif cur_humid >= 70:
        fungal_risk = "Moderate"
        fungal_score = 55
        risk_advisory = "Moderate humidity. Regular scouting recommended for early foliar spots on lower canopies."
    else:
        fungal_risk = "Low"
        fungal_score = 25
        risk_advisory = "Dry foliage conditions reduce fungal sporulation risks. Normal monitoring."

    market_benchmarks = [
        {"crop": "Sugarcane", "benchmark_type": "FRP (Fair & Remunerative Price)", "price_range": "₹315 - ₹340 / quintal", "trend": "Stable (Sugar mill crushing active)", "portal": "Agmarknet / TNAU DEMIC"},
        {"crop": "Cotton (Medium/Long)", "benchmark_type": "MSP (Govt of India)", "price_range": "₹6,620 - ₹7,520 / quintal", "trend": "Strong (+3.5% this month)", "portal": "CCI / e-NAM APMC"},
        {"crop": "Groundnut (in shell)", "benchmark_type": "MSP Benchmark", "price_range": "₹6,377 - ₹6,783 / quintal", "trend": "Steady (High edible oil demand)", "portal": "Agmarknet / e-NAM"},
        {"crop": "Paddy / Rice (Common)", "benchmark_type": "MSP (Procurement Rate)", "price_range": "₹2,183 - ₹2,300 / quintal", "trend": "Consistent (PDS procurement)", "portal": "Tamil Nadu CSC"}
    ]

    sensor = latest_sensor_reading()

    # Annual analytics query params
    year = request.args.get("year", 2025, type=int)
    crop = request.args.get("crop", "Sugarcane", type=str)
    annual_analytics = get_annual_analytics_data(year=year, crop=crop)

    return jsonify({
        "weather_trend": weather_history,
        "disease_risk": {
            "level": fungal_risk,
            "score_pct": fungal_score,
            "advisory": risk_advisory,
            "temp_c": cur_temp,
            "humidity_pct": cur_humid,
            "rain_mm": cur_precip
        },
        "market_benchmarks": market_benchmarks,
        "annual_analytics": annual_analytics,
        "latest_sensor": sensor
    })


@app.route("/api/trends/annual")
def annual_trends_endpoint():
    """Return specific multi-year, month-by-month agro-climatic, crop growth, mandi price, yield, and benefit dataset."""
    year = request.args.get("year", 2025, type=int)
    crop = request.args.get("crop", "Sugarcane", type=str)
    return jsonify(get_annual_analytics_data(year=year, crop=crop))


import agriculture_docs


# -------------------------------------------------------------
# Farm Records & Irrigation Reports Endpoints
# -------------------------------------------------------------
@app.route("/api/documents")
def documents_list_endpoint():
    """List stored farm records & documents, available government welfare schemes, and public bank interest rates."""
    category = request.args.get("category")
    docs = agriculture_docs.get_all_documents(category=category)
    schemes = agriculture_schemes_market.get_schemes()
    bank_rates = agriculture_schemes_market.get_bank_interest_rates()
    return jsonify({
        "success": True,
        "count": len(docs),
        "documents": docs,
        "categories": agriculture_docs.CATEGORIES,
        "gov_portals": agriculture_docs.GOV_PORTALS,
        "schemes": schemes,
        "bank_rates": bank_rates
    })


@app.route("/api/documents/upload", methods=["POST"])
def documents_upload_endpoint():
    """Upload a new farm document (Patta/Chitta, EB Bill, Tax, Survey FMB, Water Bill, Crop Bill, etc.)."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file attached."}), 400
    file_obj = request.files["file"]
    if not file_obj.filename:
        return jsonify({"success": False, "error": "No file selected."}), 400

    doc_type = request.form.get("doc_type", "other")
    title = request.form.get("title", file_obj.filename)
    notes = request.form.get("notes", "")

    try:
        saved = agriculture_docs.save_uploaded_document(file_obj, doc_type, title, notes)
        return jsonify({"success": True, "document": saved}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/documents/file/<int:doc_id>")
def documents_serve_endpoint(doc_id):
    """View or download a stored farm document."""
    download = request.args.get("download", "0") == "1"
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        doc = conn.execute("SELECT * FROM farm_documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    filename = doc["filename"]
    return send_from_directory(
        agriculture_docs.DOCS_DIR,
        filename,
        as_attachment=download,
        download_name=filename
    )


@app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
def documents_delete_endpoint(doc_id):
    """Delete a document."""
    success = agriculture_docs.delete_document(doc_id)
    if success:
        return jsonify({"success": True, "deleted_id": doc_id})
    return jsonify({"success": False, "error": "Document not found or delete failed"}), 404


@app.route("/api/irrigation/report/download")
def irrigation_report_download_endpoint():
    """Download live precision irrigation & sensor telemetry CSV report."""
    csv_content = agriculture_docs.generate_live_irrigation_report_csv()
    filename = f"irrigation_sensor_audit_{timestamp()[:10]}.csv"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


import agriculture_tasks
import agriculture_schemes_market


# -------------------------------------------------------------
# Daily Activities & Farm Tasks Endpoints
# -------------------------------------------------------------
@app.route("/api/tasks", methods=["GET"])
def tasks_list_endpoint():
    """List farm tasks and daily activities."""
    status = request.args.get("status")
    activity = request.args.get("activity")
    tasks = agriculture_tasks.get_tasks(status=status, activity=activity)
    summary = agriculture_tasks.get_financial_summary()
    return jsonify({
        "success": True,
        "count": len(tasks),
        "tasks": tasks,
        "summary": summary,
        "activity_types": agriculture_tasks.ACTIVITY_TYPES
    })


@app.route("/api/tasks", methods=["POST"])
def tasks_create_endpoint():
    """Create a new farm task or activity log."""
    data = request.get_json(silent=True) or request.form.to_dict()
    title = data.get("title", "")
    if not title:
        return jsonify({"success": False, "error": "Title is required"}), 400

    task_date = data.get("task_date", "")
    activity_type = data.get("activity_type", "other")
    description = data.get("description", "")
    priority = data.get("priority", "medium")
    cost_inr = float(data.get("cost_inr") or 0.0)

    try:
        new_task = agriculture_tasks.create_task(
            task_date=task_date,
            activity_type=activity_type,
            title=title,
            description=description,
            priority=priority,
            cost_inr=cost_inr
        )
        return jsonify({"success": True, "task": new_task}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/tasks/<int:task_id>/status", methods=["PATCH"])
def tasks_update_status_endpoint(task_id):
    """Toggle or update task status ('pending', 'completed', 'in_progress')."""
    data = request.get_json(silent=True) or {}
    status = data.get("status", "completed")
    success = agriculture_tasks.update_task_status(task_id, status)
    if success:
        return jsonify({"success": True, "task_id": task_id, "status": status})
    return jsonify({"success": False, "error": "Task not found or invalid status"}), 404


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def tasks_delete_endpoint(task_id):
    """Delete a farm task."""
    success = agriculture_tasks.delete_task(task_id)
    if success:
        return jsonify({"success": True, "deleted_id": task_id})
    return jsonify({"success": False, "error": "Task not found"}), 404


# -------------------------------------------------------------
# Government Schemes with Financial Support Endpoints
# -------------------------------------------------------------
@app.route("/api/schemes")
def schemes_endpoint():
    """List government agricultural welfare schemes with financial assistance & direct portal links."""
    category = request.args.get("category")
    search = request.args.get("search")
    schemes = agriculture_schemes_market.get_schemes(category=category, search=search)
    return jsonify({
        "success": True,
        "count": len(schemes),
        "schemes": schemes
    })


# -------------------------------------------------------------
# Live APMC Mandi Market Prices Endpoints
# -------------------------------------------------------------
@app.route("/api/market/prices")
def market_prices_endpoint():
    """List real-time APMC Mandi wholesale commodity rates & arrival volumes."""
    category = request.args.get("category")
    search = request.args.get("search")
    prices = agriculture_schemes_market.get_mandi_prices(category=category, search=search)
    return jsonify({
        "success": True,
        "count": len(prices),
        "prices": prices
    })


# -------------------------------------------------------------
# Publicly Available Bank Interest Rates & Agri Loans Endpoints
# -------------------------------------------------------------
@app.route("/api/bank/interest-rates")
def bank_interest_rates_endpoint():
    """List publicly available bank interest rates and agricultural credit schemes."""
    bank = request.args.get("bank")
    loan_type = request.args.get("loan_type")
    search = request.args.get("search")
    rates = agriculture_schemes_market.get_bank_interest_rates(bank=bank, loan_type=loan_type, search=search)
    return jsonify({
        "success": True,
        "count": len(rates),
        "rates": rates
    })


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)





# -------------------------------------------------------------
# ESP32 Electrical Line Fault & Pole Monitoring Endpoints
# -------------------------------------------------------------
@app.route("/api/line-fault/poles", methods=["GET"])
def line_fault_poles_endpoint():
    """Return live status of all monitored poles and feeder sections."""
    poles = esp32_line_fault.get_all_pole_telemetry()
    return jsonify({
        "success": True,
        "count": len(poles),
        "poles": poles,
        "gateway": esp32_line_fault.GATEWAY_STATE
    })


@app.route("/api/line-fault/history", methods=["GET"])
def line_fault_history_endpoint():
    """Retrieve fault logbook, frond strikes, and power failure history."""
    unresolved_only = request.args.get("unresolved", "false").lower() in ("true", "1")
    history = esp32_line_fault.get_fault_history(unresolved_only=unresolved_only)
    return jsonify({
        "success": True,
        "count": len(history),
        "history": history
    })


@app.route("/api/line-fault/simulate", methods=["POST"])
def line_fault_simulate_endpoint():
    """Simulate a line fault, coconut frond strike, or power loss on a pole."""
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    pole_id = data.get("pole_id", "P-03")
    fault_type = data.get("fault_type", "FALLEN_COCONUT_FROND")
    evidence = data.get("evidence", "")
    severity = data.get("severity", "CRITICAL")

    event = esp32_line_fault.trigger_simulated_fault(
        pole_id=pole_id,
        fault_type=fault_type,
        sensor_evidence=evidence,
        severity=severity
    )
    return jsonify({"success": True, "event": event}), 201


@app.route("/api/line-fault/resolve/<int:fault_id>", methods=["POST"])
def line_fault_resolve_endpoint(fault_id):
    """Mark a fault as cleared/resolved by TANGEDCO EB engineers."""
    success = esp32_line_fault.resolve_fault(fault_id)
    if success:
        return jsonify({"success": True, "message": f"Fault #{fault_id} marked as resolved."})
    return jsonify({"success": False, "error": "Fault record not found"}), 404


@app.route("/api/line-fault/espnow-ingest", methods=["POST"])
def line_fault_espnow_ingest():
    """Ingest packet from ESP32 Gateway receiving ESP-NOW pole frames."""
    packet = request.get_json(silent=True) or {}
    result = esp32_line_fault.receive_esp_now_packet(packet)
    return jsonify(result)


@app.route("/api/line-fault/queue-flush", methods=["POST"])
def line_fault_queue_flush():
    """Flush and synchronize queued offline packets after communication restoration."""
    flushed = esp32_line_fault.flush_offline_queue()
    return jsonify({"success": True, "flushed_count": flushed})

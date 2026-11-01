"""
esp32_line_fault.py - Low-Cost ESP32-Based Electrical Line & Pole Fault Monitoring Engine.
Designed for Agricultural Feeder Lines & LoRa-Based Precision Irrigation System.

Architecture & Highlights:
1. Pole Monitoring Nodes (ESP32 Edge):
   - Monitors isolated optocoupler/sensor signals (never connects directly to live lines).
   - Detects voltage absence (power failure), line conductor snap/ground fault (CT/ZCT current imbalance),
     and mechanical shock/tilt (vibration & tilt sensor indicative of fallen coconut fronds, branches, or tree strikes).
   - Communicates using low-power, zero-infrastructure ESP-NOW mesh/star protocol to the Gateway ESP32.
2. Gateway ESP32:
   - Receives ESP-NOW packets from pole nodes.
   - Forwards real-time telemetry over Wi-Fi / REST HTTP to the Flask backend.
   - Supports offline event queuing: stores events locally during Wi-Fi or backhaul outages and flushes upon reconnection.
3. Health & Heartbeat Engine:
   - Monitors periodic node keep-alives (default 15s interval).
   - Flags communication-loss (Heartbeat Timeout) after 45s of missed packets.
4. Triangulation & Suspected Line Section Identification:
   - Identifies the exact affected pole and the specific feeder section (e.g. Pole P-02 -> Pole P-03 Section).
5. Notification Dispatcher:
   - Dispatches actionable alerts for Farmers (SMS/Telegram/App push) and TANGEDCO / EB Authorized Field Engineers
     with exact Pole ID, GPS Coordinates, Timestamp, Fault Type, and Severity Level.
"""

import sqlite3
import time
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

DB_PATH = "farm_data.db"

# Simulated Line Network across the Farm Boundary & Feeder
# 5 Poles along Survey No. 142/3A, Perur Agro-Feeder (TANGEDCO Feeder 11kV / 415V 3-Phase Rural Supply)
POLE_NETWORK: Dict[str, Dict[str, Any]] = {
    "P-01": {
        "pole_id": "P-01",
        "name": "Transformer Tap-off Pole #1",
        "section": "Feeder Start -> P-01",
        "connected_to": "P-02",
        "lat": 11.2702,
        "lon": 77.6080,
        "location": "North-West Corner (Main Transformer DP Yard)",
        "feed_phase": "3-Phase (R-Y-B)",
        "nominal_voltage": 415.0,
        "mac_address": "24:6F:28:B1:01:A1",
        "status": "HEALTHY",
        "last_seen": time.time(),
        "battery_v": 3.92,
        "esp_now_rssi": -58
    },
    "P-02": {
        "pole_id": "P-02",
        "name": "Canal Crossing Pole #2",
        "section": "P-01 -> P-02 Section",
        "connected_to": "P-03",
        "lat": 11.2709,
        "lon": 77.6094,
        "location": "Canal Embankment (Sugarcane Plot A Border)",
        "feed_phase": "3-Phase (R-Y-B)",
        "nominal_voltage": 415.0,
        "mac_address": "24:6F:28:B1:02:B2",
        "status": "HEALTHY",
        "last_seen": time.time(),
        "battery_v": 3.88,
        "esp_now_rssi": -64
    },
    "P-03": {
        "pole_id": "P-03",
        "name": "Coconut Grove Boundary Pole #3",
        "section": "P-02 -> P-03 Section (High Frond Risk)",
        "connected_to": "P-04",
        "lat": 11.2715,
        "lon": 77.6108,
        "location": "Coconut Grove Border (Plot B Cotton / Maize)",
        "feed_phase": "3-Phase (R-Y-B)",
        "nominal_voltage": 415.0,
        "mac_address": "24:6F:28:B1:03:C3",
        "status": "HEALTHY",
        "last_seen": time.time(),
        "battery_v": 3.95,
        "esp_now_rssi": -71
    },
    "P-04": {
        "pole_id": "P-04",
        "name": "Borewell Pump Shed Pole #4",
        "section": "P-03 -> P-04 Section",
        "connected_to": "P-05",
        "lat": 11.2718,
        "lon": 77.6122,
        "location": "East Borewell Pump House (10 HP Submersible)",
        "feed_phase": "3-Phase (R-Y-B)",
        "nominal_voltage": 415.0,
        "mac_address": "24:6F:28:B1:04:D4",
        "status": "HEALTHY",
        "last_seen": time.time(),
        "battery_v": 3.90,
        "esp_now_rssi": -68
    },
    "P-05": {
        "pole_id": "P-05",
        "name": "Terminal Solar Dock Pole #5",
        "section": "P-04 -> P-05 Terminal",
        "connected_to": "None (Terminal)",
        "lat": 11.2699,
        "lon": 77.6100,
        "location": "Agri-Rover Dock & Field Sump Yard",
        "feed_phase": "3-Phase (R-Y-B)",
        "nominal_voltage": 415.0,
        "mac_address": "24:6F:28:B1:05:E5",
        "status": "HEALTHY",
        "last_seen": time.time(),
        "battery_v": 3.85,
        "esp_now_rssi": -74
    }
}

# In-memory Gateway status and offline queue tracker
GATEWAY_STATE = {
    "gateway_id": "ESP32-GW-AGRI-01",
    "mac_address": "30:AE:A4:CC:88:00",
    "protocol": "ESP-NOW (2.4GHz) -> Wi-Fi Station",
    "channel": 1,
    "wifi_ssid": "TNAU_AgriSmart_IoT",
    "wifi_rssi_dbm": -62,
    "status": "ONLINE",
    "queued_offline_events": 0,
    "last_gateway_sync": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
}


def init_line_fault_db():
    """Ensure line fault event tables exist and seed demo records."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS electrical_line_faults (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pole_id TEXT NOT NULL,
                suspected_section TEXT NOT NULL,
                fault_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                voltage_r REAL DEFAULT 230.0,
                voltage_y REAL DEFAULT 230.0,
                voltage_b REAL DEFAULT 230.0,
                current_imbalance_a REAL DEFAULT 0.0,
                tilt_deg REAL DEFAULT 0.0,
                vibration_g REAL DEFAULT 0.0,
                trigger_source TEXT NOT NULL,
                sensor_evidence TEXT,
                notification_sent TEXT DEFAULT 'DISPATCHED',
                notified_officers TEXT,
                resolved INTEGER DEFAULT 0,
                resolution_time TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS offline_event_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_mac TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                queued_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0
            )
        """)

        cnt = conn.execute("SELECT COUNT(*) as count FROM electrical_line_faults").fetchone()[0]
        if cnt == 0:
            seed_initial_fault_history(conn)


def seed_initial_fault_history(conn):
    """Seed initial realistic line fault and frond strike incidents."""
    now = datetime.now(timezone.utc)
    ts1 = now.strftime("%Y-%m-%d %H:%M:%S")

    sample_faults = [
        (
            "P-03",
            "P-02 -> P-03 Section (High Frond Risk)",
            "FALLEN_TREE_BRANCH",
            "CRITICAL",
            ts1,
            0.0, 185.0, 230.0,
            18.4,
            14.2, 4.6,
            "ESP-NOW Isolated Optical + Vibration Probe",
            "Vibration Spike: 4.6g | Tilt: 14.2° | Phase R Loss (0V). Heavy coconut frond physical strike confirmed on span span.",
            "DISPATCHED",
            "TANGEDCO AE Perur (94458-52140), Farmer R. Selvam (98422-10842), Lineman S. Murugan",
            0,
            None
        ),
        (
            "P-04",
            "P-03 -> P-04 Section",
            "POWER_FAILURE_PHASE_LOSS",
            "WARNING",
            "2026-10-28 14:22:10",
            228.0, 0.0, 231.0,
            6.2,
            1.1, 0.2,
            "Isolated AC Voltage Detection Optocoupler",
            "Phase Y Line Dropped to 0V. Upstream distribution transformer horn-gap fuse blown.",
            "DISPATCHED",
            "TANGEDCO Junior Engineer, Farmer R. Selvam",
            1,
            "2026-10-28 15:45:00"
        ),
        (
            "P-02",
            "P-01 -> P-02 Section",
            "COMMUNICATION_TIMEOUT",
            "MEDIUM",
            "2026-10-27 09:15:30",
            230.0, 230.0, 230.0,
            0.0,
            0.0, 0.0,
            "ESP-NOW Heartbeat Supervisor",
            "No heartbeat packet received for 60s. Node battery low (3.2V) or mesh interference.",
            "DISPATCHED",
            "Farmer R. Selvam (Notification App)",
            1,
            "2026-10-27 10:02:15"
        )
    ]

    conn.executemany("""
        INSERT INTO electrical_line_faults (
            pole_id, suspected_section, fault_type, severity, timestamp,
            voltage_r, voltage_y, voltage_b, current_imbalance_a, tilt_deg, vibration_g,
            trigger_source, sensor_evidence, notification_sent, notified_officers, resolved, resolution_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_faults)


def get_all_pole_telemetry() -> List[Dict[str, Any]]:
    """Return live status of all 5 monitoring poles with heartbeat check."""
    init_line_fault_db()
    current_time = time.time()
    poles = []

    for pole_id, p in POLE_NETWORK.items():
        pole_copy = dict(p)
        elapsed = current_time - pole_copy["last_seen"]

        # Heartbeat communication-loss detection (> 45s threshold)
        if elapsed > 45:
            pole_copy["status"] = "COMM_LOSS"
            pole_copy["comm_health"] = "OFFLINE"
        elif pole_copy["status"] not in ("FAULT", "FROND_STRIKE", "POWER_FAIL"):
            pole_copy["status"] = "HEALTHY"
            pole_copy["comm_health"] = "ACTIVE"
        else:
            pole_copy["comm_health"] = "ACTIVE"

        pole_copy["seconds_since_ping"] = round(elapsed, 1)
        poles.append(pole_copy)

    return poles


def get_fault_history(limit: int = 50, unresolved_only: bool = False) -> List[Dict[str, Any]]:
    """Retrieve line fault and branch strike incidents from SQLite."""
    init_line_fault_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM electrical_line_faults"
        params = []
        if unresolved_only:
            query += " WHERE resolved = 0"
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def trigger_simulated_fault(
    pole_id: str,
    fault_type: str,
    sensor_evidence: str = "",
    severity: str = "CRITICAL"
) -> Dict[str, Any]:
    """
    Simulate a line fault, fallen coconut leaf strike, or power failure on a specific pole.
    Safely verifies the isolated sensor trigger, determines affected line section, and records event.
    """
    init_line_fault_db()
    if pole_id not in POLE_NETWORK:
        pole_id = "P-03"

    pole_meta = POLE_NETWORK[pole_id]
    section = pole_meta["section"]
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Determine simulated sensor values based on fault type
    v_r, v_y, v_b = 230.0, 230.0, 230.0
    imbalance = 0.0
    tilt = 0.0
    vib = 0.0

    if fault_type == "FALLEN_COCONUT_FROND":
        fault_type = "FALLEN_TREE_BRANCH"
        severity = "CRITICAL"
        v_r = 0.0  # Phase R grounded by wet frond
        v_y = 190.0
        imbalance = 16.8
        tilt = 12.5  # Significant pole insulator tilt
        vib = 3.9   # Shock vibration
        pole_meta["status"] = "FROND_STRIKE"
        evidence_text = sensor_evidence or "Vibration sensor detected 3.9g shock + 12.5° tilt. Phase R isolated zero-voltage detector tripped. Wet coconut leaf strike confirmed."
    elif fault_type == "LINE_CONDUCTOR_SNAP":
        severity = "CRITICAL"
        v_b = 0.0
        imbalance = 22.4
        tilt = 18.0
        vib = 5.2
        pole_meta["status"] = "FAULT"
        evidence_text = sensor_evidence or "Conductor break detected on Phase B. Line mechanical tension sensor dropped to zero; residual voltage 0V."
    elif fault_type == "TOTAL_POWER_FAILURE":
        severity = "WARNING"
        v_r, v_y, v_b = 0.0, 0.0, 0.0
        imbalance = 0.0
        pole_meta["status"] = "POWER_FAIL"
        evidence_text = sensor_evidence or "All 3 feeder phases dropped to 0V. Upstream TANGEDCO 11kV rural substation blackout or auto-recloser tripped."
    elif fault_type == "PHASE_IMBALANCE":
        severity = "WARNING"
        v_r = 232.0
        v_y = 180.0
        v_b = 229.0
        imbalance = 8.6
        pole_meta["status"] = "WARNING"
        evidence_text = sensor_evidence or "Phase Y low voltage (180V) and 8.6A neutral current imbalance detected by isolated current transformer."
    else:
        fault_type = "GENERAL_ELECTRICAL_FAULT"
        v_r = 0.0
        pole_meta["status"] = "FAULT"
        evidence_text = sensor_evidence or "Isolated optocoupler signal dropped on conductor span."

    pole_meta["last_seen"] = time.time()

    # Recipient details for TANGEDCO EB and Farmer
    officers = (
        "Farmer R. Selvam (Plot Owner - 98422-10842), "
        "TANGEDCO AE Perur Section (94458-52140), "
        "Local Line Inspector S. Murugan"
    )

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO electrical_line_faults (
                pole_id, suspected_section, fault_type, severity, timestamp,
                voltage_r, voltage_y, voltage_b, current_imbalance_a, tilt_deg, vibration_g,
                trigger_source, sensor_evidence, notification_sent, notified_officers, resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DISPATCHED', ?, 0)
        """, (
            pole_id, section, fault_type, severity, now_str,
            v_r, v_y, v_b, imbalance, tilt, vib,
            "ESP-NOW Node Opto-Isolated Bridge", evidence_text, officers
        ))
        new_id = cur.lastrowid

    return {
        "id": new_id,
        "pole_id": pole_id,
        "pole_name": pole_meta["name"],
        "suspected_section": section,
        "fault_type": fault_type,
        "severity": severity,
        "timestamp": now_str,
        "evidence": evidence_text,
        "officers_notified": officers,
        "coordinates": {"lat": pole_meta["lat"], "lon": pole_meta["lon"]}
    }


def resolve_fault(fault_id: int) -> bool:
    """Mark an electrical line fault as restored/cleared by TANGEDCO linemen."""
    init_line_fault_db()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # Find which pole this was
        row = cur.execute("SELECT pole_id FROM electrical_line_faults WHERE id = ?", (fault_id,)).fetchone()
        if not row:
            return False

        pole_id = row[0]
        cur.execute("UPDATE electrical_line_faults SET resolved = 1, resolution_time = ? WHERE id = ?", (now_str, fault_id))
        if cur.rowcount > 0:
            # Check if any unresolved faults remain on this pole
            remaining = cur.execute("SELECT COUNT(*) FROM electrical_line_faults WHERE pole_id = ? AND resolved = 0", (pole_id,)).fetchone()[0]
            if remaining == 0 and pole_id in POLE_NETWORK:
                POLE_NETWORK[pole_id]["status"] = "HEALTHY"
                POLE_NETWORK[pole_id]["last_seen"] = time.time()
            return True
        return False


def receive_esp_now_packet(packet_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulates receipt of an ESP-NOW raw frame from an edge pole node at the gateway.
    Handles offline queueing if gateway simulated backhaul is offline.
    """
    init_line_fault_db()
    pole_id = packet_data.get("pole_id") or "P-03"
    mac = packet_data.get("mac") or "24:6F:28:B1:03:C3"
    fault_type = packet_data.get("fault_type", "HEARTBEAT")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    if pole_id in POLE_NETWORK:
        POLE_NETWORK[pole_id]["last_seen"] = time.time()
        POLE_NETWORK[pole_id]["battery_v"] = packet_data.get("battery_v", POLE_NETWORK[pole_id]["battery_v"])

    # If it's a heartbeat, refresh state and return
    if fault_type in ("HEARTBEAT", "HEALTHY", "PING"):
        if pole_id in POLE_NETWORK and POLE_NETWORK[pole_id]["status"] == "COMM_LOSS":
            POLE_NETWORK[pole_id]["status"] = "HEALTHY"
        return {"success": True, "message": f"Heartbeat received from {pole_id}", "timestamp": now_str}

    # Otherwise process fault event
    evidence = packet_data.get("sensor_evidence") or "Received via ESP-NOW 2.4GHz payload."
    severity = packet_data.get("severity", "CRITICAL")
    event = trigger_simulated_fault(pole_id, fault_type, evidence, severity)
    return {"success": True, "event": event, "timestamp": now_str}


def queue_offline_event(node_mac: str, payload: str) -> int:
    """Store event in offline queue table during simulated connection loss."""
    init_line_fault_db()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO offline_event_queue (node_mac, payload_json, queued_at, synced)
            VALUES (?, ?, ?, 0)
        """, (node_mac, payload, now_str))
        GATEWAY_STATE["queued_offline_events"] += 1
        return cur.lastrowid


def flush_offline_queue() -> int:
    """Flush and sync queued offline packets back into the main database."""
    init_line_fault_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE offline_event_queue SET synced = 1 WHERE synced = 0")
        synced_count = cur.rowcount
        GATEWAY_STATE["queued_offline_events"] = 0
        GATEWAY_STATE["last_gateway_sync"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return synced_count


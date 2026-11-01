
const $ = (id) => document.getElementById(id);

function showValue(id, value, suffix = "", digits = 1) {
    $(id).textContent =
        value === null || value === undefined || value === ""
            ? "Not available"
            : Number.isFinite(Number(value))
                ? `${Number(value).toFixed(digits)}${suffix}`
                : String(value);
}

function showStatus(id, message, isError = false) {
    $(id).textContent = message;
    $(id).className = "status" + (isError ? " error" : " good");
}

function showReading(id, value, suffix = "") {
    if (value === null || value === undefined) {
        $(id).textContent = "Not available";
    } else {
        showValue(id, value, suffix);
    }
}

async function loadDashboard() {
    try {
        const response = await fetch("/api/dashboard", {
            cache: "no-store"
        });
        if (!response.ok) throw new Error("Dashboard request failed");

        const data = await response.json();

        $("updated").textContent =
            new Date(data.server_time).toLocaleString();

        // NOAA ONI / ENSO
        const enso = data.enso || {};

        if (enso.value_c !== undefined) {
            showValue("enso-value", enso.value_c, " °C");
            $("enso-phase").textContent = enso.phase || "See NOAA";
            $("enso-period").textContent = enso.period || "—";
            $("enso-checked").textContent =
                "Last checked: " +
                new Date(enso.checked_at).toLocaleString();

            showStatus(
                "enso-status",
                enso.warning
                    ? "Using last successful result. NOAA check failed."
                    : enso.stale
                        ? "Previously retrieved data; refresh check failed."
                        : "NOAA data retrieved."
                    ,
                Boolean(enso.warning || enso.stale)
            );
        } else {
            $("enso-value").textContent = "Unavailable";
            $("enso-phase").textContent = "—";
            $("enso-period").textContent = "—";
            $("enso-checked").textContent = "No successful retrieval";
            showStatus(
                "enso-status",
                enso.error || "NOAA data is unavailable.",
                true
            );
        }

        // Local outdoor weather
        const weather = data.weather || {};

        if (weather.temperature_c !== undefined) {
            showValue("weather-temp", weather.temperature_c, " °C");
            showReading(
                "weather-humidity", weather.humidity_pct, " %"
            );
            showReading(
                "weather-rain", weather.precipitation_mm, " mm"
            );
            showReading(
                "weather-wind", weather.wind_speed_kmh, " km/h"
            );
            $("weather-observed").textContent =
                "Provider observation time: " +
                (weather.observed_at || "Not supplied");

            showStatus(
                "weather-status",
                weather.warning
                    ? "Using last successful weather result."
                    : "Weather data retrieved.",
                Boolean(weather.warning || weather.stale)
            );
        } else {
            $("weather-temp").textContent = "Unavailable";
            showStatus(
                "weather-status",
                weather.error || "Weather data unavailable.",
                true
            );
        }

        // Actual physical sensor data
        const sensor = data.sensor;

        if (!sensor) {
            $("soil-moisture").textContent = "Waiting...";
            $("soil-temp").textContent = "—";
            $("farm-air-temp").textContent = "Waiting...";
            $("farm-air-humidity").textContent = "—";

            showStatus(
                "soil-status",
                "No sensor readings received yet.",
                true
            );
            showStatus(
                "farm-status",
                "No sensor readings received yet.",
                true
            );
            return;
        }

        showReading(
            "soil-moisture", sensor.root_zone_moisture_pct, " %"
        );
        showReading("soil-temp", sensor.soil_temp_c, " °C");
        showReading("farm-air-temp", sensor.farm_air_temp_c, " °C");
        showReading(
            "farm-air-humidity", sensor.farm_air_humidity_pct, " %"
        );

        const age = Number(sensor.age_seconds || 0);
        const sensorMessage = `Last received ${age} seconds ago.`;

        

        showStatus(
            "soil-status",
            sensorMessage,
            age > 300
        );
        showStatus(
            "farm-status",
            sensorMessage,
            age > 300
        );

    } catch (error) {
        showStatus(
            "enso-status", "Dashboard connection failed.", true
        );
        console.error(error);
    }
}

async function postRefresh(path, buttonId) {
    const button = $(buttonId);
    button.disabled = true;

    try {
        const response = await fetch(path, { method: "POST" });
        if (!response.ok) throw new Error("Refresh failed");
        await loadDashboard();
    } catch (error) {
        alert("Could not refresh data. Check your server and internet.");
    } finally {
        button.disabled = false;
    }
}

$("refresh-enso").addEventListener("click", () => {
    postRefresh("/api/enso/refresh", "refresh-enso");
});

$("refresh-weather").addEventListener("click", () => {
    postRefresh("/api/weather/refresh", "refresh-weather");
});

// Refresh displayed data every 30 seconds.
loadDashboard();
setInterval(loadDashboard, 30000);

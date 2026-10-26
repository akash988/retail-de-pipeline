"""Central settings: paths and the cities we pull weather for."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LAKE = ROOT / "lake"
BRONZE = LAKE / "bronze"
SILVER = LAKE / "silver"
GOLD = LAKE / "gold"
LOG_DIR = ROOT / "logs"

CITIES = {
    "Mumbai":    (19.0760, 72.8777),
    "Delhi":     (28.6139, 77.2090),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai":   (13.0827, 80.2707),
    "Kolkata":   (22.5726, 88.3639),
}

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_DAILY = "temperature_2m_max,temperature_2m_min,precipitation_sum"
TIMEZONE = "Asia/Kolkata"
SERVING_DB = LAKE / "serving" / "retail.duckdb"
SQL_DIR = ROOT / "sql"
STATE_FILE = LAKE / "_state" / "state.json"
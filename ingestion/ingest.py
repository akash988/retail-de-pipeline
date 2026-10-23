"""Bronze ingestion: land raw orders, products and weather into the data lake.

Run:  python -m ingestion.ingest
"""
import argparse
import json
import logging
import re
import shutil
import time
from datetime import date
from pathlib import Path

import requests

from ingestion import config

log = logging.getLogger("ingest")


def setup_logging() -> None:
    config.LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(config.LOG_DIR / "ingest.log"),
                  logging.StreamHandler()],
    )


def ingest_orders(src_dir: Path, bronze_dir: Path, force: bool = False) -> list[str]:
    """Copy each daily file into bronze/orders/order_date=YYYY-MM-DD/.
    Idempotent: files already landed are skipped unless force=True."""
    landed, skipped = [], 0
    for f in sorted(src_dir.glob("orders_*.csv")):
        m = re.search(r"orders_(\d{4}-\d{2}-\d{2})\.csv", f.name)
        if not m:
            log.warning("Skipping unexpected file name: %s", f.name)
            continue
        day = m.group(1)
        dest = bronze_dir / "orders" / f"order_date={day}" / "orders.csv"
        if dest.exists() and not force:
            skipped += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        landed.append(day)
    log.info("Orders: landed %d files, skipped %d already present", len(landed), skipped)
    return landed


def ingest_products(src_file: Path, bronze_dir: Path) -> None:
    dest = bronze_dir / "products" / "products.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, dest)
    log.info("Products: landed %s", dest)


def fetch_weather(lat: float, lon: float, start: str, end: str, retries: int = 3) -> dict:
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": config.WEATHER_DAILY,
        "timezone": config.TIMEZONE,
    }
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(config.WEATHER_URL, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            log.warning("Weather call failed (attempt %d/%d): %s", attempt, retries, e)
            time.sleep(2 * attempt)
    raise RuntimeError("Weather API failed after retries")


def ingest_weather(start: str, end: str, run_date: str, bronze_dir: Path) -> None:
    out_dir = bronze_dir / "weather" / f"ingest_date={run_date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    for city, (lat, lon) in config.CITIES.items():
        payload = fetch_weather(lat, lon, start, end)
        payload["city"] = city
        (out_dir / f"city={city}.json").write_text(json.dumps(payload), encoding="utf-8")
        log.info("Weather: landed %s (%s to %s)", city, start, end)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run-date", default=date.today().isoformat())
    p.add_argument("--force", action="store_true")
    p.add_argument("--skip-weather", action="store_true")
    a = p.parse_args()

    setup_logging()
    log.info("=== Ingestion started | run_date=%s ===", a.run_date)

    ingest_orders(config.DATA_DIR / "orders", config.BRONZE, a.force)
    ingest_products(config.DATA_DIR / "products.csv", config.BRONZE)

    all_days = sorted(d.name.split("=")[1] for d in (config.BRONZE / "orders").glob("order_date=*"))
    if not a.skip_weather and all_days:
        ingest_weather(all_days[0], all_days[-1], a.run_date, config.BRONZE)

    log.info("=== Ingestion finished ===")


if __name__ == "__main__":
    main()
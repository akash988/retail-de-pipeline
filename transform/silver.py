"""Silver layer: clean bronze data with DuckDB and write Parquet.

Run:  python -m transform.silver
"""
import json
import logging
import shutil
from pathlib import Path

import duckdb
import pandas as pd

from ingestion import config

log = logging.getLogger("silver")

ORDERS_SQL = """
SELECT
    trim(order_id)                              AS order_id,
    TRY_CAST(order_date AS DATE)                AS order_date,
    TRY_CAST(customer_id AS INTEGER)            AS customer_id,
    trim(customer_name)                         AS customer_name,
    COALESCE(
        NULLIF(upper(left(trim(city), 1)) || lower(substr(trim(city), 2)), ''),
        'Unknown')                              AS city,
    TRY_CAST(product_id AS INTEGER)             AS product_id,
    TRY_CAST(quantity AS INTEGER)               AS quantity,
    CASE upper(trim(payment_type))
        WHEN 'UPI' THEN 'UPI'
        WHEN 'CARD' THEN 'Card'
        WHEN 'COD' THEN 'COD'
        WHEN 'NETBANKING' THEN 'NetBanking'
        ELSE 'Other'
    END                                         AS payment_type
FROM read_csv('{glob}', header=true, all_varchar=true)
WHERE order_id IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY trim(order_id) ORDER BY order_id) = 1
"""


def build_orders(con, bronze: Path, silver: Path) -> tuple[int, int]:
    glob = (bronze / "orders" / "*" / "orders.csv").as_posix()
    raw = con.execute(
        f"SELECT count(*) FROM read_csv('{glob}', header=true, all_varchar=true)"
    ).fetchall()[0][0]

    out = silver / "orders"
    if out.exists():
        shutil.rmtree(out)          # full refresh keeps reruns idempotent
    out.parent.mkdir(parents=True, exist_ok=True)

    con.execute(
        f"COPY ({ORDERS_SQL.format(glob=glob)}) TO '{out.as_posix()}' "
        f"(FORMAT PARQUET, PARTITION_BY (order_date))"
    )
    clean = con.execute(
        f"SELECT count(*) FROM read_parquet('{out.as_posix()}/**/*.parquet', hive_partitioning=true)"
    ).fetchall()[0][0]
    log.info("Orders: %d raw rows -> %d clean rows (%d removed)", raw, clean, raw - clean)
    return raw, clean


def build_products(con, bronze: Path, silver: Path) -> int:
    src = (bronze / "products" / "products.csv").as_posix()
    out = silver / "products"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    con.execute(f"""
        COPY (
            SELECT TRY_CAST(product_id AS INTEGER)      AS product_id,
                   trim(product_name)                   AS product_name,
                   trim(category)                       AS category,
                   TRY_CAST(unit_price AS DECIMAL(10,2)) AS unit_price
            FROM read_csv('{src}', header=true, all_varchar=true)
            WHERE product_id IS NOT NULL
        ) TO '{(out / "products.parquet").as_posix()}' (FORMAT PARQUET)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{(out / 'products.parquet').as_posix()}')").fetchall()[0][0]
    log.info("Products: %d rows", n)
    return n


def build_weather(con, bronze: Path, silver: Path) -> int:
    rows = []
    for f in (bronze / "weather").glob("ingest_date=*/city=*.json"):
        ingest_date = f.parent.name.split("=")[1]
        payload = json.loads(f.read_text(encoding="utf-8"))
        d = payload["daily"]
        for i, day in enumerate(d["time"]):
            rows.append({
                "city": payload["city"],
                "weather_date": day,
                "temp_max_c": d["temperature_2m_max"][i],
                "temp_min_c": d["temperature_2m_min"][i],
                "precipitation_mm": d["precipitation_sum"][i],
                "ingest_date": ingest_date,
            })
    if not rows:
        raise RuntimeError("No weather files found in bronze. Run ingestion first.")

    con.register("weather_raw", pd.DataFrame(rows))
    out = silver / "weather"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    con.execute(f"""
        COPY (
            SELECT city,
                   CAST(weather_date AS DATE)       AS weather_date,
                   CAST(temp_max_c AS DOUBLE)       AS temp_max_c,
                   CAST(temp_min_c AS DOUBLE)       AS temp_min_c,
                   CAST(precipitation_mm AS DOUBLE) AS precipitation_mm
            FROM weather_raw
            QUALIFY row_number() OVER (
                PARTITION BY city, weather_date ORDER BY ingest_date DESC) = 1
        ) TO '{(out / "weather.parquet").as_posix()}' (FORMAT PARQUET)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{(out / 'weather.parquet').as_posix()}')").fetchall()[0][0]
    log.info("Weather: %d city-day rows", n)
    return n


def run_checks(con, silver: Path) -> bool:
    orders = f"read_parquet('{(silver / 'orders').as_posix()}/**/*.parquet', hive_partitioning=true)"
    products = f"read_parquet('{(silver / 'products' / 'products.parquet').as_posix()}')"
    checks = {
        "no null order_id": f"SELECT count(*) FROM {orders} WHERE order_id IS NULL",
        "no duplicate order_id": f"SELECT count(*) - count(DISTINCT order_id) FROM {orders}",
        "quantity between 1 and 5": f"SELECT count(*) FROM {orders} WHERE quantity IS NULL OR quantity NOT BETWEEN 1 AND 5",
        "valid payment_type": f"SELECT count(*) FROM {orders} WHERE payment_type = 'Other'",
        "order_date not null": f"SELECT count(*) FROM {orders} WHERE order_date IS NULL",
        "every product_id exists": f"SELECT count(*) FROM {orders} ord LEFT JOIN {products} p ON ord.product_id = p.product_id WHERE p.product_id IS NULL",
    }
    ok = True
    for name, sql in checks.items():
        bad = con.execute(sql).fetchall()[0][0]
        if bad:
            ok = False
            log.error("QUALITY CHECK FAILED: %s (%d bad rows)", name, bad)
        else:
            log.info("quality check passed: %s", name)

    unknown = con.execute(f"SELECT count(*) FROM {orders} WHERE city = 'Unknown'").fetchall()[0][0]
    log.info("Info: %d orders have unknown city (kept, flagged as 'Unknown')", unknown)
    return ok


def main() -> None:
    config.LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(config.LOG_DIR / "silver.log"), logging.StreamHandler()],
    )
    log.info("=== Silver build started ===")
    con = duckdb.connect()
    build_orders(con, config.BRONZE, config.SILVER)
    build_products(con, config.BRONZE, config.SILVER)
    build_weather(con, config.BRONZE, config.SILVER)
    if not run_checks(con, config.SILVER):
        raise SystemExit("Silver quality checks failed")
    log.info("=== Silver build finished ===")


if __name__ == "__main__":
    main()
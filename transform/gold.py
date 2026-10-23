"""Gold layer: build a star schema + daily sales/weather summary from silver.

Run:  python -m transform.gold
"""
import logging
import shutil
from pathlib import Path

import duckdb

from ingestion import config

log = logging.getLogger("gold")

TABLES = ["dim_date", "dim_city", "dim_product", "dim_customer",
          "fact_orders", "daily_sales_summary"]


def _scalar(con, sql):
    return con.execute(sql).fetchall()[0][0]


def _create_views(con, silver: Path) -> None:
    orders = (silver / "orders").as_posix()
    products = (silver / "products" / "products.parquet").as_posix()
    weather = (silver / "weather" / "weather.parquet").as_posix()
    con.execute(f"""
        CREATE OR REPLACE VIEW s_orders AS
        SELECT order_id, CAST(order_date AS DATE) AS order_date, customer_id,
               customer_name, city, product_id, quantity, payment_type
        FROM read_parquet('{orders}/**/*.parquet', hive_partitioning=true)
    """)
    con.execute(f"CREATE OR REPLACE VIEW s_products AS SELECT * FROM read_parquet('{products}')")
    con.execute(f"CREATE OR REPLACE VIEW s_weather AS SELECT * FROM read_parquet('{weather}')")


def build_gold(con, silver: Path, gold: Path) -> dict:
    if gold.exists():
        shutil.rmtree(gold)          # full refresh keeps reruns idempotent
    gold.mkdir(parents=True)
    _create_views(con, silver)

    lo, hi = con.execute("SELECT min(order_date), max(order_date) FROM s_orders").fetchall()[0]

    con.execute(f"""
        CREATE OR REPLACE TABLE dim_date AS
        SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key,
               CAST(d AS DATE)                        AS full_date,
               year(d)                                AS year,
               month(d)                               AS month,
               monthname(d)                           AS month_name,
               day(d)                                 AS day,
               dayname(d)                             AS day_name,
               isodow(d) IN (6, 7)                    AS is_weekend
        FROM generate_series(DATE '{lo}', DATE '{hi}', INTERVAL 1 DAY) t(d)
    """)

    con.execute("""
        CREATE OR REPLACE TABLE dim_city AS
        SELECT row_number() OVER (ORDER BY city) AS city_key, city
        FROM (SELECT DISTINCT city FROM s_orders)
    """)

    con.execute("""
        CREATE OR REPLACE TABLE dim_product AS
        SELECT product_id AS product_key, product_name, category, unit_price
        FROM s_products
    """)

    con.execute("""
        CREATE OR REPLACE TABLE dim_customer AS
        SELECT customer_id AS customer_key,
               arg_max(customer_name, order_date) AS customer_name,
               min(order_date)                    AS first_order_date
        FROM s_orders
        GROUP BY customer_id
    """)

    con.execute("""
        CREATE OR REPLACE TABLE fact_orders AS
        SELECT o.order_id,
               CAST(strftime(o.order_date, '%Y%m%d') AS INTEGER) AS date_key,
               o.customer_id                                     AS customer_key,
               p.product_key,
               c.city_key,
               o.payment_type,
               o.quantity,
               p.unit_price,
               CAST(o.quantity * p.unit_price AS DECIMAL(12, 2)) AS total_amount
        FROM s_orders o
        JOIN dim_city    c ON o.city = c.city
        JOIN dim_product p ON o.product_id = p.product_key
    """)

    con.execute("""
        CREATE OR REPLACE TABLE daily_sales_summary AS
        SELECT d.full_date                       AS order_date,
               c.city,
               count(*)                          AS orders,
               sum(f.quantity)                   AS units,
               sum(f.total_amount)               AS revenue,
               round(avg(f.total_amount), 2)     AS avg_order_value,
               w.temp_max_c,
               w.temp_min_c,
               w.precipitation_mm,
               coalesce(w.precipitation_mm, 0) > 1 AS is_rainy
        FROM fact_orders f
        JOIN dim_date d ON f.date_key = d.date_key
        JOIN dim_city c ON f.city_key = c.city_key
        LEFT JOIN s_weather w ON w.city = c.city AND w.weather_date = d.full_date
        GROUP BY d.full_date, c.city, w.temp_max_c, w.temp_min_c, w.precipitation_mm
    """)

    counts = {}
    for t in TABLES:
        out = gold / t
        out.mkdir()
        path = (out / f"{t}.parquet").as_posix()
        con.execute(f"COPY (SELECT * FROM {t}) TO '{path}' (FORMAT PARQUET)")
        counts[t] = _scalar(con, f"SELECT count(*) FROM {t}")
        log.info("Gold: %-20s %6d rows", t, counts[t])
    return counts


def run_checks(con) -> bool:
    silver_rows = _scalar(con, "SELECT count(*) FROM s_orders")
    checks = {
        "fact rows equal silver rows (no join loss)":
            f"SELECT abs(count(*) - {silver_rows}) FROM fact_orders",
        "no null keys in fact":
            "SELECT count(*) FROM fact_orders WHERE date_key IS NULL OR customer_key IS NULL "
            "OR product_key IS NULL OR city_key IS NULL",
        "total_amount is positive":
            "SELECT count(*) FROM fact_orders WHERE total_amount IS NULL OR total_amount <= 0",
        "order_id unique in fact":
            "SELECT count(*) - count(DISTINCT order_id) FROM fact_orders",
        "summary revenue equals fact revenue":
            "SELECT CAST(abs((SELECT sum(total_amount) FROM fact_orders) - "
            "(SELECT sum(revenue) FROM daily_sales_summary)) AS INTEGER)",
        "dimension keys are unique":
            "SELECT (SELECT count(*) - count(DISTINCT city_key) FROM dim_city) + "
            "(SELECT count(*) - count(DISTINCT product_key) FROM dim_product) + "
            "(SELECT count(*) - count(DISTINCT customer_key) FROM dim_customer) + "
            "(SELECT count(*) - count(DISTINCT date_key) FROM dim_date)",
    }
    ok = True
    for name, sql in checks.items():
        bad = _scalar(con, sql)
        if bad:
            ok = False
            log.error("QUALITY CHECK FAILED: %s (%s)", name, bad)
        else:
            log.info("quality check passed: %s", name)
    return ok


def main() -> None:
    config.LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(config.LOG_DIR / "gold.log"), logging.StreamHandler()],
    )
    log.info("=== Gold build started ===")
    con = duckdb.connect()
    build_gold(con, config.SILVER, config.GOLD)
    if not run_checks(con):
        raise SystemExit("Gold quality checks failed")
    log.info("=== Gold build finished ===")


if __name__ == "__main__":
    main()
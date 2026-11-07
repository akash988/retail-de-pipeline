"""Export local gold tables as Parquet with types that match the Azure SQL schema.

Run:  python -m warehouse.export_for_azure
"""
import shutil

import duckdb

from ingestion import config

OUT = config.LAKE / "azure_export"

EXPORTS = {
    "dim_date": """
        SELECT CAST(date_key AS INTEGER) AS date_key, CAST(full_date AS DATE) AS full_date,
               CAST("year" AS INTEGER) AS "year", CAST("month" AS INTEGER) AS "month",
               CAST(month_name AS VARCHAR) AS month_name, CAST("day" AS INTEGER) AS "day",
               CAST(day_name AS VARCHAR) AS day_name, CAST(is_weekend AS BOOLEAN) AS is_weekend
        FROM dim_date""",
    "dim_city": """
        SELECT CAST(city_key AS INTEGER) AS city_key, CAST(city AS VARCHAR) AS city
        FROM dim_city""",
    "dim_product": """
        SELECT CAST(product_key AS INTEGER) AS product_key, CAST(product_name AS VARCHAR) AS product_name,
               CAST(category AS VARCHAR) AS category, CAST(unit_price AS DECIMAL(10,2)) AS unit_price
        FROM dim_product""",
    "dim_customer": """
        SELECT CAST(customer_key AS INTEGER) AS customer_key, CAST(customer_name AS VARCHAR) AS customer_name,
               CAST(first_order_date AS DATE) AS first_order_date
        FROM dim_customer""",
    "fact_orders": """
        SELECT CAST(order_id AS VARCHAR) AS order_id, CAST(date_key AS INTEGER) AS date_key,
               CAST(customer_key AS INTEGER) AS customer_key, CAST(product_key AS INTEGER) AS product_key,
               CAST(city_key AS INTEGER) AS city_key, CAST(payment_type AS VARCHAR) AS payment_type,
               CAST(quantity AS INTEGER) AS quantity, CAST(unit_price AS DECIMAL(10,2)) AS unit_price,
               CAST(total_amount AS DECIMAL(12,2)) AS total_amount
        FROM fact_orders""",
    "daily_sales_summary": """
        SELECT CAST(order_date AS DATE) AS order_date, CAST(city AS VARCHAR) AS city,
               CAST(orders AS INTEGER) AS orders, CAST(units AS INTEGER) AS units,
               CAST(revenue AS DECIMAL(14,2)) AS revenue,
               CAST(avg_order_value AS DECIMAL(12,2)) AS avg_order_value,
               CAST(temp_max_c AS DOUBLE) AS temp_max_c, CAST(temp_min_c AS DOUBLE) AS temp_min_c,
               CAST(precipitation_mm AS DOUBLE) AS precipitation_mm,
               CAST(is_rainy AS BOOLEAN) AS is_rainy
        FROM daily_sales_summary""",
}


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    con = duckdb.connect(str(config.SERVING_DB), read_only=True)
    try:
        for name, sql in EXPORTS.items():
            folder = OUT / name
            folder.mkdir(parents=True)
            path = (folder / f"{name}.parquet").as_posix()
            con.execute(f"COPY ({sql}) TO '{path}' (FORMAT PARQUET)")
            n = con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchall()[0][0]
            print(f"{name:<22}{n:>8} rows")
    finally:
        con.close()


if __name__ == "__main__":
    main()
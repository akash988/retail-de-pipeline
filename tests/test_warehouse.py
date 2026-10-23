import duckdb

from warehouse.load import load_warehouse


def _write(con, gold, name, select_sql):
    d = gold / name
    d.mkdir(parents=True)
    con.execute(f"COPY ({select_sql}) TO '{(d / (name + '.parquet')).as_posix()}' (FORMAT PARQUET)")


def test_load_creates_tables_and_views(tmp_path):
    gold = tmp_path / "gold"
    con = duckdb.connect()
    _write(con, gold, "dim_date", "SELECT 20261001 AS date_key, DATE '2026-10-01' AS full_date, 'Thursday' AS day_name, false AS is_weekend")
    _write(con, gold, "dim_city", "SELECT 1 AS city_key, 'Mumbai' AS city")
    _write(con, gold, "dim_product", "SELECT 1 AS product_key, 'P1' AS product_name, 'Home' AS category, 100.0 AS unit_price")
    _write(con, gold, "dim_customer", "SELECT 1001 AS customer_key, 'Ravi' AS customer_name")
    _write(con, gold, "fact_orders", "SELECT 'A1' AS order_id, 20261001 AS date_key, 1001 AS customer_key, 1 AS product_key, 1 AS city_key, 'UPI' AS payment_type, 2 AS quantity, 100.0 AS unit_price, 200.0 AS total_amount")
    _write(con, gold, "daily_sales_summary", "SELECT DATE '2026-10-01' AS order_date, 'Mumbai' AS city, 1 AS orders, 2 AS units, 200.0 AS revenue, 200.0 AS avg_order_value, 33.0 AS temp_max_c, 26.0 AS temp_min_c, 5.0 AS precipitation_mm, true AS is_rainy")

    views = tmp_path / "views.sql"
    views.write_text(
        "-- test view\nCREATE VIEW vw_revenue_by_city AS "
        "SELECT c.city, sum(f.total_amount) AS revenue "
        "FROM fact_orders f JOIN dim_city c USING (city_key) GROUP BY c.city;\n")

    db = tmp_path / "wh" / "retail.duckdb"
    counts = load_warehouse(gold, db, views)
    assert counts["fact_orders"] == 1

    # loading twice must work (idempotent)
    load_warehouse(gold, db, views)
    out = duckdb.connect(str(db)).execute(
        "SELECT city, revenue FROM vw_revenue_by_city").fetchall()
    assert out == [("Mumbai", 200.0)]
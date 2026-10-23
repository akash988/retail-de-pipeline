import duckdb

from transform.gold import build_gold, run_checks


def _make_silver(con, silver):
    (silver / "orders").mkdir(parents=True)
    (silver / "products").mkdir(parents=True)
    (silver / "weather").mkdir(parents=True)
    con.execute(f"""
        COPY (SELECT * FROM (VALUES
            ('A1', DATE '2026-10-01', 1001, 'Ravi', 'Mumbai',  1, 2, 'UPI'),
            ('A2', DATE '2026-10-01', 1002, 'Sita', 'Unknown', 2, 1, 'Card'),
            ('A3', DATE '2026-10-02', 1001, 'Ravi', 'Mumbai',  1, 1, 'COD')
        ) t(order_id, order_date, customer_id, customer_name, city, product_id, quantity, payment_type))
        TO '{(silver / "orders" / "orders.parquet").as_posix()}' (FORMAT PARQUET)
    """)
    con.execute(f"""
        COPY (SELECT * FROM (VALUES
            (1, 'P1', 'Home',    CAST(100.00 AS DECIMAL(10,2))),
            (2, 'P2', 'Fashion', CAST(50.00  AS DECIMAL(10,2)))
        ) t(product_id, product_name, category, unit_price))
        TO '{(silver / "products" / "products.parquet").as_posix()}' (FORMAT PARQUET)
    """)
    con.execute(f"""
        COPY (SELECT * FROM (VALUES
            ('Mumbai', DATE '2026-10-01', 33.0, 26.0, 5.0)
        ) t(city, weather_date, temp_max_c, temp_min_c, precipitation_mm))
        TO '{(silver / "weather" / "weather.parquet").as_posix()}' (FORMAT PARQUET)
    """)


def test_gold_star_schema(tmp_path):
    silver, gold = tmp_path / "silver", tmp_path / "gold"
    con = duckdb.connect()
    _make_silver(con, silver)

    counts = build_gold(con, silver, gold)

    assert counts["fact_orders"] == 3
    assert counts["dim_city"] == 2          # Mumbai + Unknown
    assert run_checks(con) is True

    row = con.execute(
        "SELECT orders, revenue, is_rainy FROM daily_sales_summary "
        "WHERE city = 'Mumbai' AND order_date = DATE '2026-10-01'"
    ).fetchall()[0]
    assert row[0] == 1 and float(row[1]) == 200.0 and row[2] is True
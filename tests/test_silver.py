import duckdb

from transform.silver import build_orders


def test_orders_are_cleaned_and_deduplicated(tmp_path):
    bronze, silver = tmp_path / "bronze", tmp_path / "silver"
    d = bronze / "orders" / "order_date=2026-10-01"
    d.mkdir(parents=True)
    (d / "orders.csv").write_text(
        "order_id,order_date,customer_id,customer_name,city,product_id,quantity,payment_type\n"
        "A1,2026-10-01,1001,Ravi,  mumbai ,1,2,upi\n"
        "A1,2026-10-01,1001,Ravi,  mumbai ,1,2,upi\n"
        "A2,2026-10-01,1002,Sita,,2,1,Card\n"
    )
    con = duckdb.connect()
    raw, clean = build_orders(con, bronze, silver)

    assert (raw, clean) == (3, 2)
    path = (silver / "orders").as_posix()
    rows = con.execute(
        f"SELECT order_id, city, payment_type "
        f"FROM read_parquet('{path}/**/*.parquet', hive_partitioning=true) ORDER BY order_id"
    ).fetchall()
    assert rows == [("A1", "Mumbai", "UPI"), ("A2", "Unknown", "Card")]
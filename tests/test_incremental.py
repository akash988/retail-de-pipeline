import duckdb

from transform.silver import build_orders_incremental
from transform.state import file_hash, load_state, save_state

HEADER = "order_id,order_date,customer_id,customer_name,city,product_id,quantity,payment_type\n"


def _write_day(bronze, day, rows):
    d = bronze / "orders" / f"order_date={day}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "orders.csv").write_text(HEADER + rows)


def _count(con, silver):
    path = (silver / "orders").as_posix()
    return con.execute(
        f"SELECT count(*) FROM read_parquet('{path}/**/*.parquet', hive_partitioning=true)"
    ).fetchall()[0][0]


def test_incremental_skips_unchanged_and_handles_new_and_changed_days(tmp_path):
    bronze, silver, state = tmp_path / "bronze", tmp_path / "silver", tmp_path / "state.json"
    con = duckdb.connect()

    _write_day(bronze, "2026-10-01", "A1,2026-10-01,1001,Ravi,Mumbai,1,2,UPI\n")
    r1 = build_orders_incremental(con, bronze, silver, state)
    assert r1["days_processed"] == 1 and _count(con, silver) == 1

    r2 = build_orders_incremental(con, bronze, silver, state)       # nothing new
    assert r2["days_processed"] == 0 and r2["days_skipped"] == 1

    _write_day(bronze, "2026-10-02", "B1,2026-10-02,1002,Sita,Delhi,2,1,Card\n")
    r3 = build_orders_incremental(con, bronze, silver, state)       # one new day
    assert r3["days_processed"] == 1 and _count(con, silver) == 2
    assert load_state(state)["watermark"] == "2026-10-02"

    _write_day(bronze, "2026-10-01",                                  # late correction to an old day
               "A1,2026-10-01,1001,Ravi,Mumbai,1,2,UPI\n"
               "A2,2026-10-01,1003,Amit,Delhi,1,1,COD\n")
    r4 = build_orders_incremental(con, bronze, silver, state)
    assert r4["days_processed"] == 1 and _count(con, silver) == 3


def test_state_roundtrip_and_hash(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("x")
    h1 = file_hash(f)
    f.write_text("y")
    assert file_hash(f) != h1

    s = tmp_path / "st" / "state.json"
    assert load_state(s) == {}
    save_state(s, {"watermark": "2026-10-01"})
    assert load_state(s)["watermark"] == "2026-10-01"
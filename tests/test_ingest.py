from ingestion.ingest import ingest_orders


def test_ingest_orders_is_idempotent(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "orders_2026-10-01.csv").write_text("order_id\nA1\n")
    bronze = tmp_path / "bronze"

    first = ingest_orders(src, bronze)
    second = ingest_orders(src, bronze)

    assert first == ["2026-10-01"]
    assert second == []
    assert (bronze / "orders" / "order_date=2026-10-01" / "orders.csv").exists()
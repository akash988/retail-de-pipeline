import pandas as pd

from dashboard.metrics import apply_filters, compute_kpis


def _df():
    return pd.DataFrame({
        "order_id": ["A1", "A2", "A3"],
        "full_date": pd.to_datetime(["2026-10-01", "2026-10-02", "2026-10-03"]),
        "city": ["Mumbai", "Delhi", "Mumbai"],
        "category": ["Home", "Fashion", "Home"],
        "quantity": [1, 2, 3],
        "total_amount": [100.0, 200.0, 300.0],
    })


def test_compute_kpis():
    k = compute_kpis(_df())
    assert k["revenue"] == 600.0
    assert k["orders"] == 3
    assert k["units"] == 6
    assert k["avg_order_value"] == 200.0


def test_apply_filters():
    out = apply_filters(_df(), "2026-10-01", "2026-10-02", ["Mumbai"], ["Home", "Fashion"])
    assert list(out["order_id"]) == ["A1"]


def test_kpis_on_empty_frame():
    empty = _df().iloc[0:0]
    assert compute_kpis(empty)["avg_order_value"] == 0.0
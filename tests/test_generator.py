from datetime import date
from data_generator.generate_data import make_orders, make_products


def test_orders_have_expected_columns():
    df = make_orders(date(2026, 10, 1), 100, 20)
    assert {"order_id", "order_date", "customer_id", "city",
            "product_id", "quantity", "payment_type"} <= set(df.columns)
    assert len(df) >= 100


def test_products_count():
    assert len(make_products(20)) == 20
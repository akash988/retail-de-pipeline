"""Dashboard helpers: filtering and KPI calculation."""
import pandas as pd


def apply_filters(df: pd.DataFrame, start, end, cities, categories) -> pd.DataFrame:
    mask = (
        (df["full_date"] >= pd.Timestamp(start))
        & (df["full_date"] <= pd.Timestamp(end))
        & df["city"].isin(cities)
        & df["category"].isin(categories)
    )
    return df[mask]


def compute_kpis(df: pd.DataFrame) -> dict:
    orders = int(df["order_id"].nunique())
    revenue = float(df["total_amount"].sum())
    return {
        "revenue": revenue,
        "orders": orders,
        "units": int(df["quantity"].sum()),
        "avg_order_value": revenue / orders if orders else 0.0,
    }
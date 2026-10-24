"""Retail analytics dashboard.

Run:  streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard.metrics import apply_filters, compute_kpis  # noqa: E402

DB = ROOT / "lake" / "serving" / "retail.duckdb"

st.set_page_config(page_title="Retail Analytics", page_icon="📊", layout="wide")


@st.cache_data(ttl=60)
def query(sql: str) -> pd.DataFrame:
    # read_only + short-lived connection so the pipeline can still write
    con = duckdb.connect(str(DB), read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


if not DB.exists():
    st.error("Warehouse not found. Run `python -m pipeline.run_pipeline` first.")
    st.stop()

orders = query("""
    SELECT f.order_id, d.full_date, d.day_name, d.is_weekend,
           c.city, p.category, f.payment_type, f.quantity,
           CAST(f.total_amount AS DOUBLE) AS total_amount
    FROM fact_orders f
    JOIN dim_date d    USING (date_key)
    JOIN dim_city c    USING (city_key)
    JOIN dim_product p USING (product_key)
""")
orders["full_date"] = pd.to_datetime(orders["full_date"])

weather = query("""
    SELECT order_date, city, orders, CAST(revenue AS DOUBLE) AS revenue,
           temp_max_c, precipitation_mm, is_rainy
    FROM daily_sales_summary
""")
weather["order_date"] = pd.to_datetime(weather["order_date"])

# ---------------- sidebar filters ----------------
st.sidebar.header("Filters")
min_d, max_d = orders["full_date"].min().date(), orders["full_date"].max().date()
date_range = st.sidebar.date_input("Date range", (min_d, max_d), min_value=min_d, max_value=max_d)
if len(date_range) != 2:
    st.info("Pick both a start and an end date.")
    st.stop()

all_cities = sorted(orders["city"].unique())
all_cats = sorted(orders["category"].unique())
cities = st.sidebar.multiselect("City", all_cities, default=all_cities)
cats = st.sidebar.multiselect("Category", all_cats, default=all_cats)

df = apply_filters(orders, date_range[0], date_range[1], cities, cats)
if df.empty:
    st.warning("No data for the selected filters.")
    st.stop()

wdf = weather[
    (weather["order_date"] >= pd.Timestamp(date_range[0]))
    & (weather["order_date"] <= pd.Timestamp(date_range[1]))
    & weather["city"].isin(cities)
]

# ---------------- header + KPIs ----------------
st.title("📊 Retail Sales and Weather Analytics")
st.caption("Source: local lakehouse pipeline (bronze → silver → gold → DuckDB warehouse). "
           "Order data is synthetic.")

k = compute_kpis(df)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", f"₹{k['revenue']:,.0f}")
c2.metric("Orders", f"{k['orders']:,}")
c3.metric("Units sold", f"{k['units']:,}")
c4.metric("Avg order value", f"₹{k['avg_order_value']:,.0f}")

tab1, tab2, tab3, tab4 = st.tabs(["Sales", "Weather", "Data quality", "Pipeline runs"])

# ---------------- sales ----------------
with tab1:
    st.subheader("Daily revenue")
    st.line_chart(df.groupby("full_date")["total_amount"].sum())

    left, right = st.columns(2)
    with left:
        st.subheader("Revenue by city")
        st.bar_chart(df.groupby("city")["total_amount"].sum().sort_values(ascending=False))
        st.subheader("Payment mix (orders)")
        st.bar_chart(df.groupby("payment_type")["order_id"].nunique())
    with right:
        st.subheader("Revenue by category")
        st.bar_chart(df.groupby("category")["total_amount"].sum().sort_values(ascending=False))
        st.subheader("Weekday vs weekend (avg daily revenue)")
        daily = df.groupby(["full_date", "is_weekend"])["total_amount"].sum().reset_index()
        daily["type"] = daily["is_weekend"].map({True: "Weekend", False: "Weekday"})
        st.bar_chart(daily.groupby("type")["total_amount"].mean())

# ---------------- weather ----------------
with tab2:
    st.caption("Orders are randomly generated, so no real weather effect is expected here. "
               "The point is that the pipeline joins the two sources correctly.")
    wd = wdf.dropna(subset=["precipitation_mm"])
    if wd.empty:
        st.info("No weather data in this selection.")
    else:
        a, b = st.columns(2)
        with a:
            st.subheader("Avg daily revenue: rainy vs dry")
            r = wd.groupby("is_rainy")["revenue"].mean()
            r.index = r.index.map({True: "Rainy", False: "Dry"})
            st.bar_chart(r)
        with b:
            st.subheader("Max temperature vs revenue")
            st.scatter_chart(wd, x="temp_max_c", y="revenue")
        st.subheader("Weather and revenue detail")
        st.dataframe(wd.sort_values(["order_date", "city"], ascending=[False, True]),
                     use_container_width=True, hide_index=True)

# ---------------- data quality ----------------
with tab3:
    st.subheader("Data quality snapshot")
    unknown = int((orders["city"] == "Unknown").sum())
    q1, q2, q3 = st.columns(3)
    q1.metric("Orders in warehouse", f"{orders['order_id'].nunique():,}")
    q2.metric("Duplicate order IDs", f"{len(orders) - orders['order_id'].nunique():,}")
    q3.metric("Orders with unknown city", f"{unknown:,}")
    st.write("Duplicates are removed in silver and unknown cities are flagged rather than dropped.")

# ---------------- pipeline runs ----------------
with tab4:
    st.subheader("Recent pipeline runs")
    try:
        runs = query("""SELECT run_id, step, status, started_at, duration_s, attempts
                        FROM pipeline_runs ORDER BY started_at DESC LIMIT 40""")
        st.dataframe(runs, use_container_width=True, hide_index=True)
    except Exception:
        st.info("No run history yet. Run the pipeline once with `python -m pipeline.run_pipeline`.")
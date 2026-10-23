import duckdb

con = duckdb.connect()
G = "lake/gold"


def show(title, sql):
    print(f"\n=== {title} ===")
    print(con.sql(sql))


show("Revenue by city",
     f"""SELECT c.city, count(*) AS orders, sum(f.total_amount) AS revenue
         FROM read_parquet('{G}/fact_orders/*.parquet') f
         JOIN read_parquet('{G}/dim_city/*.parquet') c USING (city_key)
         GROUP BY c.city ORDER BY revenue DESC""")

show("Revenue by category",
     f"""SELECT p.category, sum(f.total_amount) AS revenue
         FROM read_parquet('{G}/fact_orders/*.parquet') f
         JOIN read_parquet('{G}/dim_product/*.parquet') p USING (product_key)
         GROUP BY p.category ORDER BY revenue DESC""")

show("Rainy vs dry days (avg daily revenue per city)",
     f"""SELECT is_rainy, count(*) AS city_days, round(avg(revenue), 2) AS avg_revenue
         FROM read_parquet('{G}/daily_sales_summary/*.parquet')
         WHERE precipitation_mm IS NOT NULL
         GROUP BY is_rainy""")

show("Weekend vs weekday",
     f"""SELECT d.is_weekend, round(avg(s.revenue), 2) AS avg_revenue
         FROM read_parquet('{G}/daily_sales_summary/*.parquet') s
         JOIN read_parquet('{G}/dim_date/*.parquet') d ON s.order_date = d.full_date
         GROUP BY d.is_weekend""")
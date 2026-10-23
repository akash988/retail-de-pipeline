-- Reporting views on top of the star schema. Rebuilt on every warehouse load.

CREATE VIEW vw_revenue_by_city AS
SELECT c.city,
       count(*)                      AS orders,
       sum(f.total_amount)           AS revenue,
       round(avg(f.total_amount), 2) AS avg_order_value
FROM fact_orders f
JOIN dim_city c USING (city_key)
GROUP BY c.city;

CREATE VIEW vw_revenue_by_category AS
SELECT p.category,
       sum(f.quantity)     AS units,
       sum(f.total_amount) AS revenue
FROM fact_orders f
JOIN dim_product p USING (product_key)
GROUP BY p.category;

CREATE VIEW vw_daily_revenue AS
SELECT d.full_date,
       d.day_name,
       d.is_weekend,
       count(*)            AS orders,
       sum(f.total_amount) AS revenue
FROM fact_orders f
JOIN dim_date d USING (date_key)
GROUP BY d.full_date, d.day_name, d.is_weekend;

CREATE VIEW vw_payment_mix AS
SELECT payment_type,
       count(*)            AS orders,
       sum(total_amount)   AS revenue
FROM fact_orders
GROUP BY payment_type;

CREATE VIEW vw_weather_impact AS
SELECT is_rainy,
       count(*)                AS city_days,
       round(avg(revenue), 2)  AS avg_daily_revenue,
       round(avg(orders), 1)   AS avg_daily_orders
FROM daily_sales_summary
WHERE precipitation_mm IS NOT NULL
GROUP BY is_rainy;

CREATE VIEW vw_top_customers AS
SELECT cu.customer_key,
       cu.customer_name,
       count(*)            AS orders,
       sum(f.total_amount) AS total_spent
FROM fact_orders f
JOIN dim_customer cu USING (customer_key)
GROUP BY cu.customer_key, cu.customer_name
ORDER BY total_spent DESC
LIMIT 20;
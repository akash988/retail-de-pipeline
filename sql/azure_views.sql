EXEC('CREATE OR ALTER VIEW gold.vw_revenue_by_city AS
SELECT c.city, COUNT(*) AS orders, SUM(f.total_amount) AS revenue,
       CAST(AVG(f.total_amount) AS DECIMAL(12,2)) AS avg_order_value
FROM gold.fact_orders f JOIN gold.dim_city c ON f.city_key = c.city_key
GROUP BY c.city');

EXEC('CREATE OR ALTER VIEW gold.vw_revenue_by_category AS
SELECT p.category, SUM(f.quantity) AS units, SUM(f.total_amount) AS revenue
FROM gold.fact_orders f JOIN gold.dim_product p ON f.product_key = p.product_key
GROUP BY p.category');

EXEC('CREATE OR ALTER VIEW gold.vw_daily_revenue AS
SELECT d.full_date, d.day_name, d.is_weekend, COUNT(*) AS orders, SUM(f.total_amount) AS revenue
FROM gold.fact_orders f JOIN gold.dim_date d ON f.date_key = d.date_key
GROUP BY d.full_date, d.day_name, d.is_weekend');

EXEC('CREATE OR ALTER VIEW gold.vw_payment_mix AS
SELECT payment_type, COUNT(*) AS orders, SUM(total_amount) AS revenue
FROM gold.fact_orders GROUP BY payment_type');

EXEC('CREATE OR ALTER VIEW gold.vw_weather_impact AS
SELECT is_rainy, COUNT(*) AS city_days,
       CAST(AVG(revenue) AS DECIMAL(14,2)) AS avg_daily_revenue,
       CAST(AVG(CAST(orders AS FLOAT)) AS DECIMAL(10,1)) AS avg_daily_orders
FROM gold.daily_sales_summary
WHERE precipitation_mm IS NOT NULL
GROUP BY is_rainy');
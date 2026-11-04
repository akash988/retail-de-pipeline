CREATE SCHEMA gold;
CREATE TABLE gold.dim_date (
  date_key INT NOT NULL PRIMARY KEY,
  full_date DATE NOT NULL,
  [year] INT, [month] INT, month_name VARCHAR(20),
  [day] INT, day_name VARCHAR(20), is_weekend BIT
);

CREATE TABLE gold.dim_city (
  city_key INT NOT NULL PRIMARY KEY,
  city VARCHAR(50) NOT NULL
);

CREATE TABLE gold.dim_product (
  product_key INT NOT NULL PRIMARY KEY,
  product_name VARCHAR(100), category VARCHAR(50), unit_price DECIMAL(10,2)
);

CREATE TABLE gold.dim_customer (
  customer_key INT NOT NULL PRIMARY KEY,
  customer_name VARCHAR(100), first_order_date DATE
);

CREATE TABLE gold.fact_orders (
  order_id VARCHAR(30) NOT NULL PRIMARY KEY,
  date_key INT NOT NULL, customer_key INT NOT NULL,
  product_key INT NOT NULL, city_key INT NOT NULL,
  payment_type VARCHAR(20), quantity INT,
  unit_price DECIMAL(10,2), total_amount DECIMAL(12,2)
);

CREATE TABLE gold.daily_sales_summary (
  order_date DATE NOT NULL, city VARCHAR(50) NOT NULL,
  orders INT, units INT, revenue DECIMAL(14,2), avg_order_value DECIMAL(12,2),
  temp_max_c FLOAT, temp_min_c FLOAT, precipitation_mm FLOAT, is_rainy BIT,
  PRIMARY KEY (order_date, city)
);
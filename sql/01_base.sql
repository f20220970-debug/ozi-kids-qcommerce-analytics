-- Clean base tables. Kids = baby, toys, diapers & hygiene, children's clothes (the closest Olist categories to OZi's range).
CREATE OR REPLACE VIEW cat AS
SELECT p.product_id, coalesce(t.product_category_name_english, 'unknown') AS category,
       coalesce(t.product_category_name_english, '') IN ('baby','toys','diapers_and_hygiene','fashion_childrens_clothes') AS is_kids
FROM read_csv_auto('data/olist_products_dataset.csv') p
LEFT JOIN read_csv_auto('data/product_category_name_translation.csv') t USING (product_category_name);

CREATE OR REPLACE VIEW items AS
SELECT i.order_id, i.order_item_id, i.product_id, i.seller_id, i.price, i.freight_value, c.category, c.is_kids
FROM read_csv_auto('data/olist_order_items_dataset.csv') i JOIN cat c USING (product_id);

-- one review per order (latest), since a few orders have several
CREATE OR REPLACE VIEW reviews AS
SELECT order_id, review_score, review_comment_message AS comment
FROM read_csv_auto('data/olist_order_reviews_dataset.csv', all_varchar=true)
QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) = 1;

CREATE OR REPLACE TABLE orders AS
WITH o AS (
  SELECT o.*, c.customer_unique_id, c.customer_city, c.customer_state
  FROM read_csv_auto('data/olist_orders_dataset.csv') o
  JOIN read_csv_auto('data/olist_customers_dataset.csv') c USING (customer_id)
), agg AS (
  SELECT order_id, bool_or(is_kids) AS has_kids, bool_and(is_kids) AS all_kids, count(*) AS n_items,
         sum(price) AS gmv, sum(freight_value) AS freight, count(DISTINCT seller_id) AS n_sellers,
         arg_max(category, price) AS main_category
  FROM items GROUP BY order_id
)
SELECT o.order_id, o.customer_unique_id, o.customer_city, o.customer_state, o.order_status,
       o.order_purchase_timestamp AS purchased_at,
       o.order_delivered_customer_date AS delivered_at,
       o.order_estimated_delivery_date AS promised_at,
       date_diff('hour', o.order_purchase_timestamp, o.order_delivered_customer_date) / 24.0 AS delivery_days,
       o.order_delivered_customer_date > o.order_estimated_delivery_date + INTERVAL 1 DAY AS is_late,
       a.has_kids, a.all_kids, a.n_items, a.gmv, a.freight, a.n_sellers, a.main_category,
       try_cast(r.review_score AS INT) AS review_score, r.comment
FROM o JOIN agg a USING (order_id) LEFT JOIN reviews r USING (order_id);
SELECT count(*) AS orders, sum(has_kids::INT) AS kids_orders FROM orders;

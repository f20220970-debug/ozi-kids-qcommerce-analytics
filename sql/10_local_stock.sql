-- Local stock: orders where every seller is in the customer's state vs shipped from another state.
-- Split by customer region so the comparison isn't just "Sao Paulo vs everyone else".
WITH s AS (SELECT seller_id, seller_state FROM read_csv_auto('data/olist_sellers_dataset.csv')),
o2 AS (
  SELECT o.order_id, any_value(o.has_kids) AS has_kids, any_value(o.customer_state) AS cust_state,
         any_value(o.delivery_days) AS dd, any_value(o.is_late) AS late, any_value(o.review_score) AS score,
         bool_and(s.seller_state = o.customer_state) AS same_state
  FROM orders o JOIN items i USING (order_id) JOIN s USING (seller_id)
  WHERE o.order_status = 'delivered' AND o.delivered_at IS NOT NULL GROUP BY o.order_id
)
SELECT CASE WHEN cust_state = 'SP' THEN 'customer in SP' ELSE 'customer outside SP' END AS region,
       CASE WHEN same_state THEN 'seller in same state' ELSE 'seller in another state' END AS stock,
       count(*) AS orders, round(avg(dd), 1) AS avg_delivery_days, round(100 * avg(late::INT), 1) AS pct_late,
       round(avg(score), 2) AS avg_score
FROM o2 GROUP BY ALL ORDER BY region, stock;

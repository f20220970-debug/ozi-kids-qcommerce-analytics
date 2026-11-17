-- Density: quick commerce works city by city. How concentrated is kids demand?
WITH c AS (
  SELECT customer_city, customer_state, count(*) AS kids_orders, round(avg(delivery_days), 1) AS avg_delivery_days,
         round(100 * avg(is_late::INT), 1) AS pct_late, round(avg(review_score), 2) AS avg_score
  FROM orders WHERE has_kids AND order_status = 'delivered' GROUP BY ALL
)
SELECT *, round(100.0 * kids_orders / sum(kids_orders) OVER (), 1) AS pct_of_kids_orders,
       round(100.0 * sum(kids_orders) OVER (ORDER BY kids_orders DESC ROWS UNBOUNDED PRECEDING) / sum(kids_orders) OVER (), 1) AS cum_pct
FROM c ORDER BY kids_orders DESC LIMIT 10;

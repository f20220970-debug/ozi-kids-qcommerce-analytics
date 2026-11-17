-- Repeat purchase: share of customers who order again within 180 days of their first order, by first-order type.
WITH firsts AS (
  SELECT customer_unique_id, min(purchased_at) AS first_at, arg_min(has_kids, purchased_at) AS first_has_kids
  FROM orders WHERE order_status NOT IN ('canceled','unavailable') GROUP BY 1
), nexts AS (
  SELECT f.customer_unique_id, f.first_at, f.first_has_kids,
         min(o.purchased_at) FILTER (WHERE o.purchased_at > f.first_at + INTERVAL 1 HOUR) AS second_at,
         arg_min(o.has_kids, o.purchased_at) FILTER (WHERE o.purchased_at > f.first_at + INTERVAL 1 HOUR) AS second_has_kids
  FROM firsts f JOIN orders o USING (customer_unique_id)
  WHERE o.order_status NOT IN ('canceled','unavailable') AND f.first_at < TIMESTAMP '2018-03-01'   -- full 180-day window
  GROUP BY f.customer_unique_id, f.first_at, f.first_has_kids
)
SELECT CASE WHEN first_has_kids THEN 'first order had kids items' ELSE 'first order other' END AS cohort,
       count(*) AS customers,
       round(100 * avg(coalesce(second_at <= first_at + INTERVAL 180 DAY, false)::INT), 2) AS pct_repeat_180d,
       median(date_diff('day', first_at, second_at)) FILTER (WHERE second_at <= first_at + INTERVAL 180 DAY) AS median_days_to_2nd,
       round(100 * avg(second_has_kids::INT) FILTER (WHERE second_at <= first_at + INTERVAL 180 DAY), 1) AS pct_2nd_order_kids
FROM nexts GROUP BY ALL ORDER BY cohort;

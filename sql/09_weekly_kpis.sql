-- Weekly metric pack (the dashboard a product analyst would own): kids orders, AOV, late %, avg score, new vs repeat.
WITH f AS (SELECT customer_unique_id, min(purchased_at) AS first_at FROM orders GROUP BY 1)
SELECT date_trunc('week', purchased_at)::DATE AS week, count(*) AS kids_orders,
       round(avg(gmv), 1) AS aov_brl, round(100 * avg(is_late::INT), 1) AS pct_late,
       round(avg(review_score), 2) AS avg_score,
       round(100 * avg((purchased_at > first_at + INTERVAL 1 HOUR)::INT), 1) AS pct_repeat_customers
FROM orders JOIN f USING (customer_unique_id)
WHERE has_kids AND purchased_at BETWEEN TIMESTAMP '2017-01-01' AND TIMESTAMP '2018-08-20'
GROUP BY ALL ORDER BY week;

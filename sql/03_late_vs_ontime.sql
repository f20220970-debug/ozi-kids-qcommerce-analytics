-- Broken promise vs slow: is it the speed or missing the promised date that hurts?
SELECT CASE WHEN has_kids THEN 'kids' ELSE 'other' END AS segment,
       CASE WHEN is_late THEN 'late (missed promised date)' ELSE 'on time' END AS promise,
       count(*) AS orders, round(avg(delivery_days), 1) AS avg_delivery_days,
       round(avg(review_score), 2) AS avg_score, round(100 * avg((review_score <= 2)::INT), 1) AS pct_1_2_star
FROM orders
WHERE order_status = 'delivered' AND delivered_at IS NOT NULL AND review_score IS NOT NULL
GROUP BY ALL ORDER BY segment, promise;

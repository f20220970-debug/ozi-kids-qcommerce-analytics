-- Does speed matter to satisfaction? Review score by delivery time, kids vs other orders (delivered orders with a review).
SELECT CASE WHEN has_kids THEN 'kids' ELSE 'other' END AS segment,
       CASE WHEN delivery_days < 3 THEN '1: <3 days' WHEN delivery_days < 7 THEN '2: 3-6 days'
            WHEN delivery_days < 14 THEN '3: 7-13 days' WHEN delivery_days < 21 THEN '4: 14-20 days' ELSE '5: 21+ days' END AS delivery_bucket,
       count(*) AS orders,
       round(avg(review_score), 2) AS avg_score,
       round(100 * avg((review_score <= 2)::INT), 1) AS pct_1_2_star,
       round(100 * avg((review_score = 5)::INT), 1) AS pct_5_star
FROM orders
WHERE order_status = 'delivered' AND delivered_at IS NOT NULL AND review_score IS NOT NULL
GROUP BY ALL ORDER BY segment, delivery_bucket;

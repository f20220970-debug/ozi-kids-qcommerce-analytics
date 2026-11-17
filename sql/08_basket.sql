-- Basket economics: kids vs other orders (delivered).
SELECT CASE WHEN has_kids THEN 'kids' ELSE 'other' END AS segment, count(*) AS orders,
       round(avg(gmv), 1) AS avg_order_value_brl, round(median(gmv), 1) AS median_order_value_brl,
       round(avg(n_items), 2) AS avg_items, round(100 * avg((n_items > 1)::INT), 1) AS pct_multi_item,
       round(100 * sum(freight) / sum(gmv), 1) AS freight_pct_of_gmv,
       round(100 * avg((n_sellers > 1)::INT), 1) AS pct_multi_seller
FROM orders WHERE order_status = 'delivered' GROUP BY ALL ORDER BY segment;

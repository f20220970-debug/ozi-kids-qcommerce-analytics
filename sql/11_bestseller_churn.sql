-- Do kids bestsellers last? Top 50 kids SKUs in Jul-Dec 2017, and what happened to them in Jan-Jun 2018.
WITH s AS (SELECT i.product_id, o.purchased_at AS ts FROM items i JOIN orders o USING (order_id) WHERE i.is_kids),
h1 AS (SELECT product_id, count(*) AS u FROM s WHERE ts BETWEEN '2017-07-01' AND '2017-12-31' GROUP BY 1 ORDER BY u DESC, product_id LIMIT 50),
h2all AS (SELECT product_id, count(*) AS u FROM s WHERE ts BETWEEN '2018-01-01' AND '2018-06-30' GROUP BY 1),
h2 AS (SELECT product_id FROM h2all ORDER BY u DESC, product_id LIMIT 50)
SELECT (SELECT count(*) FROM h1 WHERE product_id IN (SELECT product_id FROM h2)) AS still_in_top50_next_half,
       (SELECT count(*) FROM h1 WHERE product_id NOT IN (SELECT product_id FROM h2all)) AS zero_sales_next_half,
       (SELECT round(100 * sum(u) / (SELECT sum(u) FROM h2all), 1) FROM h2all WHERE product_id IN (SELECT product_id FROM h1)) AS pct_next_half_units_from_old_top50,
       (SELECT round(100 * sum(u) / (SELECT sum(u) FROM h2all), 1) FROM h2all WHERE product_id IN (SELECT product_id FROM h2)) AS pct_next_half_units_from_new_top50;

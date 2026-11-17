-- Dark-store assortment: how few kids SKUs cover most demand? (units sold per product, kids categories)
WITH s AS (
  SELECT product_id, category, count(*) AS units FROM items WHERE is_kids GROUP BY ALL
), r AS (
  SELECT *, sum(units) OVER (ORDER BY units DESC, product_id ROWS UNBOUNDED PRECEDING) / sum(units) OVER () AS cum_share,
         row_number() OVER (ORDER BY units DESC, product_id) AS rank_
  FROM s
)
SELECT target_share, min(rank_) AS skus_needed, (SELECT count(*) FROM s) AS total_skus,
       round(100.0 * min(rank_) / (SELECT count(*) FROM s), 1) AS pct_of_skus
FROM r, (VALUES (0.5), (0.8), (0.9)) v(target_share)
WHERE cum_share >= target_share GROUP BY target_share ORDER BY target_share;

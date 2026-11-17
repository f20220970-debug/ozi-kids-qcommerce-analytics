-- Why do 1-2 star reviewers complain? Portuguese phrase rules on review comments (delivered or not).
WITH bad AS (
  SELECT CASE WHEN has_kids THEN 'kids' ELSE 'other' END AS segment, lower(comment) AS c
  FROM orders WHERE review_score <= 2 AND comment IS NOT NULL AND length(comment) > 3
)
SELECT segment, count(*) AS bad_reviews_with_text,
  round(100 * avg(regexp_matches(c, 'n[aã]o (recebi|chegou|foi entregue|entreg)|ainda n[aã]o|atras|prazo|demor')::INT), 1) AS pct_delivery_delay_or_not_received,
  round(100 * avg(regexp_matches(c, 'errad|diferente|faltando|falta|incomplet|veio (s[oó]|apenas|somente)|outro produto|trocad')::INT), 1) AS pct_wrong_or_missing_item,
  round(100 * avg(regexp_matches(c, 'defeito|quebrad|danific|qualidade|n[aã]o funciona|rasgad|amassad')::INT), 1) AS pct_defect_or_quality,
  round(100 * avg(regexp_matches(c, 'atendimento|n[aã]o responde|sem resposta|contato')::INT), 1) AS pct_support_unresponsive
FROM bad GROUP BY ALL ORDER BY segment;

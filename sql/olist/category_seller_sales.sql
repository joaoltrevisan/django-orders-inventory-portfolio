-- Attribute merchandise/freight to source item sellers, never allocate order payments.
WITH sales AS (
 SELECT category.source_name AS source_category, category.english_name AS english_category,
        s.source_seller_id, COUNT(*) AS units, COUNT(DISTINCT o.id) AS associated_orders,
        SUM(i.price) AS merchandise_value, SUM(i.freight_value) AS freight_value
 FROM olist_order_item i INNER JOIN olist_order o ON o.id=i.order_id
 INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
 INNER JOIN olist_product p ON p.id=i.product_id
 INNER JOIN olist_seller s ON s.id=i.seller_id
 LEFT JOIN olist_category category ON category.id=p.category_id
 WHERE o.source_status='delivered'
 AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
 GROUP BY category.source_name,category.english_name,s.source_seller_id
 HAVING COUNT(*) >= %(min_units)s
)
SELECT *, ROW_NUMBER() OVER (
 PARTITION BY source_category ORDER BY merchandise_value DESC, source_seller_id
) AS seller_position_within_category
FROM sales ORDER BY source_category NULLS FIRST, merchandise_value DESC, source_seller_id;

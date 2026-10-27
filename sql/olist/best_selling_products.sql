-- Each historical item row is one observed source unit, never order_item_id units.
WITH sales AS (
 SELECT p.source_product_id, COUNT(*) AS units, COUNT(DISTINCT o.id) AS orders,
        SUM(i.price) AS merchandise_value
 FROM olist_order_item i
 INNER JOIN olist_order o ON o.id=i.order_id
 INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
 INNER JOIN olist_product p ON p.id=i.product_id
 WHERE o.source_status='delivered'
   AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
 GROUP BY p.source_product_id HAVING COUNT(*) >= %(min_units)s
)
SELECT *, DENSE_RANK() OVER (ORDER BY units DESC) AS units_rank,
       ROW_NUMBER() OVER (ORDER BY units DESC, merchandise_value DESC, source_product_id) AS display_position
FROM sales ORDER BY units DESC, merchandise_value DESC, source_product_id;

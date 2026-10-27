-- One source item per row. Include every source status; payments are not joined.
SELECT o.source_order_id, o.source_status, o.purchased_at_source,
       c.source_customer_id, c.customer_unique_id, p.source_product_id,
       category.source_name AS source_category,
       COALESCE(category.english_name,
                CASE WHEN category.id IS NULL THEN 'Missing category' ELSE 'Untranslated category' END) AS category_label,
       s.source_seller_id, i.source_order_item_id, i.price AS historical_unit_price,
       i.freight_value
FROM olist_order o
INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
INNER JOIN olist_customer c ON c.id=o.customer_id
INNER JOIN olist_order_item i ON i.order_id=o.id
INNER JOIN olist_product p ON p.id=i.product_id
INNER JOIN olist_seller s ON s.id=i.seller_id
LEFT JOIN olist_category category ON category.id=p.category_id
WHERE o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
ORDER BY o.source_order_id, i.source_order_item_id;

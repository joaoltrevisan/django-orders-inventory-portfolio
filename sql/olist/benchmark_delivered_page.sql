-- Frozen experiment query: a delivered-order history page in a fixed source purchase interval.
SELECT o.source_order_id,o.purchased_at_source,c.customer_unique_id
FROM olist_order o INNER JOIN olist_customer c ON c.id=o.customer_id
WHERE o.source_status='delivered'
AND o.snapshot_id=(SELECT id FROM olist_dataset_snapshot WHERE publication_status='COMPLETE')
AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
ORDER BY o.purchased_at_source,o.source_order_id LIMIT %(row_limit)s;

-- Customer reference grain, not repeat identity. Eligibility stays inside LEFT JOIN.
SELECT c.source_customer_id, c.customer_unique_id,
       COUNT(o.id) AS orders_all_statuses,
       COUNT(o.id) FILTER (WHERE o.source_status='delivered') AS delivered_orders
FROM olist_customer c
INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=c.snapshot_id AND snapshot.publication_status='COMPLETE'
LEFT JOIN olist_order o ON o.customer_id=c.id
 AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
GROUP BY c.id, c.source_customer_id, c.customer_unique_id
ORDER BY c.source_customer_id;

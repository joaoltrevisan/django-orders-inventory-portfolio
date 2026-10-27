-- Repeat means at least two delivered orders within this observation window.
WITH customers AS (
 SELECT c.customer_unique_id,COUNT(*) AS delivered_orders
 FROM olist_order o INNER JOIN olist_customer c ON c.id=o.customer_id
 INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
 WHERE o.source_status='delivered'
 AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
 GROUP BY c.customer_unique_id
)
SELECT COUNT(*) AS eligible_customer_identities,
       COUNT(*) FILTER (WHERE delivered_orders>=2) AS repeat_customer_identities,
       ROUND(100.0*COUNT(*) FILTER (WHERE delivered_orders>=2)/NULLIF(COUNT(*),0),2) AS repeat_customer_percent
FROM customers;

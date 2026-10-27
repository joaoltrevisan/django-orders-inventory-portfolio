-- Include observed identities without eligible orders; zeros describe observed merchandise only.
WITH identities AS (
 SELECT DISTINCT c.customer_unique_id FROM olist_customer c
 INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=c.snapshot_id AND snapshot.publication_status='COMPLETE'
), items AS (
 SELECT order_id,SUM(price) AS merchandise FROM olist_order_item GROUP BY order_id
), spending AS (
 SELECT c.customer_unique_id, COUNT(*) AS delivered_orders,
        SUM(i.merchandise) AS merchandise_value,
        COUNT(*) FILTER (WHERE i.order_id IS NULL) AS orders_without_items
 FROM olist_order o INNER JOIN olist_customer c ON c.id=o.customer_id
 INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
 LEFT JOIN items i ON i.order_id=o.id
 WHERE o.source_status='delivered'
 AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
 GROUP BY c.customer_unique_id
), totals AS (
 SELECT c.customer_unique_id, COALESCE(s.delivered_orders,0) AS delivered_orders,
        COALESCE(s.merchandise_value,0) AS observed_merchandise_value,
        COALESCE(s.orders_without_items,0) AS orders_without_items
 FROM identities c LEFT JOIN spending s ON s.customer_unique_id=c.customer_unique_id
)
SELECT *, DENSE_RANK() OVER (ORDER BY observed_merchandise_value DESC) AS spending_rank
FROM totals ORDER BY observed_merchandise_value DESC, customer_unique_id;

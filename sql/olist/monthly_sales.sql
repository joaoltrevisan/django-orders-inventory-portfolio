-- Independent fact aggregation prevents item x payment multiplication.
WITH items AS (
 SELECT order_id, SUM(price) AS merchandise, SUM(freight_value) AS freight FROM olist_order_item GROUP BY order_id
), payments AS (
 SELECT order_id, SUM(payment_value) AS recorded_value FROM olist_payment_record GROUP BY order_id
)
SELECT date_trunc('month',o.purchased_at_source)::date AS month,
       COUNT(*) AS delivered_orders, SUM(i.merchandise) AS merchandise_value,
       SUM(i.freight) AS freight_value, SUM(p.recorded_value) AS recorded_payment_value,
       COUNT(*) FILTER (WHERE i.order_id IS NULL) AS orders_without_items,
       COUNT(*) FILTER (WHERE p.order_id IS NULL) AS orders_without_payments
FROM olist_order o
INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
LEFT JOIN items i ON i.order_id=o.id LEFT JOIN payments p ON p.order_id=o.id
WHERE o.source_status='delivered'
 AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
GROUP BY date_trunc('month',o.purchased_at_source)::date ORDER BY month;

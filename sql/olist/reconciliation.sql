-- All source statuses. A missing fact is NULL and flagged; recorded zero stays zero.
WITH items AS (
 SELECT order_id,SUM(price) AS merchandise,SUM(freight_value) AS freight FROM olist_order_item GROUP BY order_id
), payments AS (
 SELECT order_id,SUM(payment_value) AS recorded_payment FROM olist_payment_record GROUP BY order_id
)
SELECT o.source_order_id,o.source_status,i.merchandise,i.freight,p.recorded_payment,
       i.order_id IS NULL AS missing_items,p.order_id IS NULL AS missing_payments,
       p.recorded_payment-i.merchandise-i.freight AS payment_minus_items_and_freight
FROM olist_order o
INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
LEFT JOIN items i ON i.order_id=o.id LEFT JOIN payments p ON p.order_id=o.id
WHERE o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
AND (i.order_id IS NULL OR p.order_id IS NULL OR ABS(p.recorded_payment-i.merchandise-i.freight) > 0.01)
ORDER BY o.source_order_id;

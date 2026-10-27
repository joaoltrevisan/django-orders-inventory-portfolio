-- Distinct order/seller associations: repeated seller items do not duplicate delivery outcomes.
WITH associations AS (
 SELECT DISTINCT order_id,seller_id FROM olist_order_item
), deliveries AS (
 SELECT s.source_seller_id,o.delivered_customer_at_source,o.estimated_delivery_at_source,
   (o.delivered_customer_at_source IS NOT NULL AND o.estimated_delivery_at_source IS NOT NULL
    AND o.delivered_customer_at_source >= o.purchased_at_source
    AND o.estimated_delivery_at_source::date >= o.purchased_at_source::date) AS timing_valid
 FROM associations a INNER JOIN olist_order o ON o.id=a.order_id
 INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
 INNER JOIN olist_seller s ON s.id=a.seller_id
 WHERE o.source_status='delivered'
 AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
)
SELECT source_seller_id,COUNT(*) AS associated_delivered_orders,
 COUNT(*) FILTER (WHERE timing_valid) AS eligible_associations,
 COUNT(*) FILTER (WHERE NOT timing_valid) AS excluded_associations,
 COUNT(*) FILTER (WHERE timing_valid AND delivered_customer_at_source::date <= estimated_delivery_at_source::date) AS on_time_associations
FROM deliveries GROUP BY source_seller_id ORDER BY source_seller_id;

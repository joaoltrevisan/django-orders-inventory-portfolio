-- Order-level timing only. Missing/negative date pairs stay in the excluded denominator.
WITH deliveries AS (
 SELECT o.*, c.state,
   (o.delivered_customer_at_source IS NOT NULL AND o.estimated_delivery_at_source IS NOT NULL
    AND o.delivered_customer_at_source >= o.purchased_at_source
    AND o.estimated_delivery_at_source::date >= o.purchased_at_source::date) AS timing_valid
 FROM olist_order o INNER JOIN olist_customer c ON c.id=o.customer_id
 INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
 WHERE o.source_status='delivered'
 AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
)
SELECT date_trunc('month',purchased_at_source)::date AS purchase_month, state,
 COUNT(*) AS delivered_orders, COUNT(*) FILTER (WHERE timing_valid) AS eligible_orders,
 COUNT(*) FILTER (WHERE NOT timing_valid) AS excluded_orders,
 COUNT(*) FILTER (WHERE timing_valid AND delivered_customer_at_source::date <= estimated_delivery_at_source::date) AS on_time_orders,
 ROUND(100.0 * COUNT(*) FILTER (WHERE timing_valid AND delivered_customer_at_source::date <= estimated_delivery_at_source::date)
       / NULLIF(COUNT(*) FILTER (WHERE timing_valid),0),2) AS on_time_percent,
 AVG((delivered_customer_at_source::date - estimated_delivery_at_source::date)::numeric)
       FILTER (WHERE timing_valid) AS average_signed_calendar_delay_days
FROM deliveries GROUP BY date_trunc('month',purchased_at_source)::date,state
ORDER BY purchase_month,state;

-- Zero-filled requested source-calendar months; boundary months may be partial.
WITH calendar AS (
 SELECT generate_series(date_trunc('month',%(start)s::timestamp),
                        date_trunc('month',%(end)s::timestamp-interval '1 microsecond'),interval '1 month')::date AS month
), items AS (
 SELECT order_id, SUM(price) AS merchandise FROM olist_order_item GROUP BY order_id
), monthly AS (
 SELECT date_trunc('month',o.purchased_at_source)::date AS month,
        SUM(i.merchandise) AS merchandise_value, COUNT(*) AS delivered_orders,
        COUNT(*) FILTER (WHERE i.order_id IS NULL) AS orders_without_items
 FROM olist_order o
 INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
 LEFT JOIN items i ON i.order_id=o.id
 WHERE o.source_status='delivered'
 AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
 GROUP BY date_trunc('month',o.purchased_at_source)::date
)
SELECT c.month, COALESCE(m.merchandise_value,0) AS observed_merchandise_value,
       COALESCE(m.delivered_orders,0) AS delivered_orders,
       COALESCE(m.orders_without_items,0) AS orders_without_items,
       SUM(COALESCE(m.merchandise_value,0)) OVER (
         ORDER BY c.month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS running_observed_merchandise_value
FROM calendar c LEFT JOIN monthly m ON m.month=c.month ORDER BY c.month;

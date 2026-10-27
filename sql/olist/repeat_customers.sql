-- One eligible order before grouping repeat identity across customer references.
WITH items AS (
 SELECT order_id, SUM(price) AS merchandise FROM olist_order_item GROUP BY order_id
), customers AS (
 SELECT c.customer_unique_id, COUNT(*) AS delivered_orders,
        SUM(i.merchandise) AS merchandise_value,
        COUNT(*) FILTER (WHERE i.order_id IS NULL) AS orders_without_items
 FROM olist_order o
 INNER JOIN olist_dataset_snapshot snapshot ON snapshot.id=o.snapshot_id AND snapshot.publication_status='COMPLETE'
 INNER JOIN olist_customer c ON c.id=o.customer_id
 LEFT JOIN items i ON i.order_id=o.id
 WHERE o.source_status='delivered'
  AND o.purchased_at_source >= %(start)s::timestamp AND o.purchased_at_source < %(end)s::timestamp
 GROUP BY c.customer_unique_id HAVING COUNT(*) >= %(min_orders)s
)
SELECT *, DENSE_RANK() OVER (ORDER BY merchandise_value DESC NULLS LAST) AS spending_rank
FROM customers ORDER BY merchandise_value DESC NULLS LAST, customer_unique_id;

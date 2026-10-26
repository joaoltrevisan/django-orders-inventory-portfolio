# Olist source dictionary and proposed mappings

Status: inspected source and proposed mapping. Models/import/API are not implemented yet. Source string values remain unchanged even when they are Portuguese; code identifiers, normalized column names, analytical labels, comments, and documentation are English.

## Identity and row grain

| Source field/key | Meaning and proposed representation |
| --- | --- |
| `customer_id` | Source customer record attached to an order; preserve as unique `source_customer_id`, not a login ID |
| `customer_unique_id` | Anonymized identifier grouping repeat customers across source customer rows; nonunique indexed field on historical customers; not evidence of a known real-world identity |
| `order_id` | Unique historical order identifier, stored as `source_order_id` |
| `(order_id, order_item_id)` | Unique source item-line key; `order_item_id` is a positive line sequence, **not quantity**; each source row represents one purchased unit |
| `product_id`, `seller_id` | Preserve as `source_product_id` and `source_seller_id`; each item references both; sellers/products have no source commercial name fields |
| `(order_id, payment_sequential)` | Unique recorded payment row; one order can have multiple payment methods/rows |

Use surrogate bigint application PKs plus unique source keys for historical tables. Retain raw identifiers as exact 32-character source strings where applicable; do not relabel them as UUIDs. Initially one immutable snapshot is permitted per isolated database, so source-key uniqueness does not need to mix several dataset versions. Changing the source snapshot requires a fresh database.

## Source file mapping

| File / observed rows | Source columns | Proposed meaning and null handling |
| --- | --- | --- |
| `olist_customers_dataset.csv` / 99,441 | `customer_id`, `customer_unique_id`, `customer_zip_code_prefix`, `customer_city`, `customer_state` | Customer reference, repeat identity, purchase-location snapshot; postal prefix is text of five digits, not a complete address. No name/email/password inferred |
| `olist_products_dataset.csv` / 32,951 | `product_id`, `product_category_name` | Historical product identity and nullable source category; no SKU, name, current price, stock, or activation flag is supplied |
| Same file | `product_name_lenght`, `product_description_lenght`, `product_photos_qty` | Nullable integer metadata; normalize misspelled source headings to `name_length`, `description_length`, `photos_count` and preserve the mapping. A name length is not a product name |
| Same file | `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm` | Nullable weight/dimensions with units retained in normalized column names; 2 rows lack these measurements |
| `product_category_name_translation.csv` / 71 | `product_category_name`, `product_category_name_english` | Original category key and supplied English label. Build category rows from product/translation union, retaining missing English labels as null |
| `olist_sellers_dataset.csv` / 3,095 | `seller_id`, `seller_zip_code_prefix`, `seller_city`, `seller_state` | Historical seller identity and location; no merchant name, login, listing price, or live offer inferred |
| `olist_orders_dataset.csv` / 99,441 | `order_id`, `customer_id`, `order_status` | Source order and customer FK; preserve original status spelling, including `canceled` |
| Same file | `order_purchase_timestamp`, `order_approved_at` | Source purchase time and nullable order approval time. Approval is not a per-payment timestamp or proof of cash settlement |
| Same file | `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_estimated_delivery_date` | Nullable carrier/customer delivery facts and estimate at **order** level; not seller/item shipment tracking. Preserve raw timestamp strings and parsed timezone-free values |
| `olist_order_items_dataset.csv` / 112,650 | `order_id`, `order_item_id`, `product_id`, `seller_id` | One source unit/line; repeated products and multiple sellers are valid. Do not aggregate during import |
| Same file | `price`, `freight_value`, `shipping_limit_date` | Observed item price, item freight, and source shipping deadline. Decimal money; not today's real catalog price or actual shipment time |
| `olist_order_payments_dataset.csv` / 103,886 | `order_id`, `payment_sequential`, `payment_type`, `payment_installments`, `payment_value` | Recorded payment facts; do not multiply amount by installment count. Zero amount/installments and `not_defined` type remain preserved and flagged where relevant |
| `olist_order_reviews_dataset.csv` / 99,224 | `review_id`, `order_id`, `review_score`, optional text, review timestamps | Inspected/fingerprinted but deferred from initial import. Review ID/order alone are not unique; a later import requires a validated key such as the observed pair `(review_id, order_id)` |
| `olist_geolocation_dataset.csv` / 1,000,163 | Postal prefix, latitude, longitude, city, state | Inspected/fingerprinted but deferred. A postal prefix is not assumed unique; a later location join must first define aggregation and cardinality |

The complete exact headers, file sizes, SHA-256 hashes and blank-cell counts are in the [executed profile](../../reports/olist/inspection-profile.json). No raw review text is published or used for identity inference.

## Historical status vocabulary

| Raw status | Observed orders | Treatment |
| --- | ---: | --- |
| `delivered` | 96,478 | Default merchandise-analysis inclusion; timing analyses require their own valid-date checks |
| `shipped` | 1,107 | Preserve; exclude from default delivered-order sales; optional explicitly scoped pipeline analysis |
| `canceled` | 625 | Preserve spelling/dates/payments; exclude from default delivered-order sales; never run simulated cancellation |
| `unavailable` | 609 | Preserve; no synthetic inventory explanation or stock restoration |
| `invoiced` | 314 | Preserve; no claimed settlement or simulated payment mapping |
| `processing` | 301 | Preserve; no inferred operational transition |
| `created` | 5 | Preserve; no automatic stock reservation |
| `approved` | 2 | Preserve; no assumption of a simulated `PAID` state |

No historical state is rewritten into the demonstration lifecycle. Completeness/chronology flags are separate from raw status. In particular, a delivered order with a missing approval or delivery date remains delivered in the source representation.

## Time, money, and derived measures

Source timestamps are offset-free. Store raw source text plus validated naive parsed values; missing values remain null. Initial reports group by the source calendar without claiming a verified geographic time zone. Simulated events continue using aware UTC timestamps. For delivered-on-time analysis compare actual and estimated **calendar dates**, publish the eligible denominator, and exclude invalid/missing date pairs. Duration metrics use valid nonnegative source differences and disclose that absolute instants are not established.

Keep these measures distinct: `merchandise_value = SUM(item.price)`, `freight_value = SUM(item.freight_value)`, `expected_recorded_charge = merchandise_value + freight_value`, and `recorded_payment_value = SUM(payment.payment_value)`. Aggregate each fact table to one row per order before joining. A missing side is null/absent with a flag, not an observed zero. Payment/order differences are observed data-quality facts, not automatic import rejection or permission to alter source records.

No seller payment allocation, net revenue, profit, refund ledger, chargeback history, inventory, customer credentials, live product price, seller-specific shipment timeline, or operational cancellation timestamp is supplied. All corresponding demonstration fields/events must be labeled simulated. The [adaptation plan](adaptation-plan.md) defines the boundary and future tests.

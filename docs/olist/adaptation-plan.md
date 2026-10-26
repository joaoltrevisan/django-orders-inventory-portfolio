# Olist case-study adaptation plan

Status: proposal for technical review. This delivery inspects source data and revises the design; it does not implement database models, an importer, or an API.

This is an independent educational case study using the public [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). It does not imply employment, partnership, endorsement, or access to Olist's internal systems.

## Starting point and preserved work

The current repository contains the Stage 1 design and review at commit `3a40eba`, not a running application. The existing API implementation remains in the separate `loja-pedidos-estoque` repository at `21b5b17`. Both working trees were clean before this adaptation. No existing database, volume, configuration, or source file in that related project has been changed.

Continue the new repository by selectively adapting that API's Django modules, password/JWT mechanisms, validation, transactional services, PostgreSQL tests, and Docker setup. Do not claim that code has already been ported, and do not regenerate an unrelated application from scratch.

Keep Python, Django/DRF, PostgreSQL, JWT, Docker/Compose, English artifacts/commits, an independent reviewer, actual verification evidence, and the user's technical-review checkpoint. The earlier JWT dependency compatibility qualification remains open. This plan supersedes the fictional-only and single-seller portions of the initial Stage 1 documents; those documents remain historical records.

## Inspection before changes

The actual public ZIP was downloaded into an isolated temporary directory and inspected with Python's CSV, ZIP, and decimal libraries. The [inspection record](inspection.md) and committed aggregate profile record source metadata, hashes, exact file/row counts, key checks, relationships, and anomalies. This is executed CSV evidence, not SQL-query output or benchmark evidence.

The archive contains 99,441 orders, 112,650 item rows, 103,886 payment rows, 99,441 customer rows, 96,096 distinct anonymized customer identities, 32,951 products, and 3,095 sellers. All eight source order statuses must be preserved. The source contains no complete operational inventory, account credentials, current product prices, or real payment-processing integration.

## Conflicts and proposed corrections

| Existing assumption | Observed source conflict | Proposed correction |
| --- | --- | --- |
| A customer profile belongs to a login user | Source customers have anonymized identifiers and purchase-location attributes, not accounts | Keep historical customers separate from Django users and simulated customer profiles |
| One customer ID is the repeat buyer identity | Source `customer_id` occurs once per order in this archive, while `customer_unique_id` repeats | Join orders by `customer_id`; group repeat-customer metrics by `customer_unique_id` |
| One product line per order | 7,088 order/product groups repeat | Key historical lines by `(order_id, order_item_id)`; retain every line |
| One store fulfills every item | 1,278 orders contain multiple sellers | Store seller on every historical line; add seller offers to the simulation |
| Product has one current price and stock balance | Source products have neither; 5,435 product/seller pairs have multiple observed item prices | Store prices only as historical item facts; simulated current price and stock belong to a seller/product offer |
| One approved payment equals the order total | 2,961 orders have multiple payment rows, and 303 comparable orders differ by more than BRL 0.01 | Preserve payment sequences and amounts; reconcile independently aggregated amounts without repairing source records |
| Every payment amount/installment count is positive | 9 zero-value payments and 2 zero-installment records exist | Preserve nonnegative source values and flag anomalies; simulation rules remain strict |
| Strict lifecycle and complete delivery timestamps | Source statuses differ; delivered orders have missing dates, and 6 canceled orders have a delivery timestamp | Preserve source statuses and nullable timestamps; flag inconsistencies without inventing transitions |
| Every order has items/payment | 775 orders have no item rows and 1 has no payment rows | Retain orders, distinguish missing facts from observed zero amounts, and report completeness |
| UTC timestamps are always source facts | CSV timestamps contain no offset and metadata does not establish the time zone | Preserve raw/timezone-free source values; never silently claim converted UTC instants are observed |
| Every product has a complete name/address/category | Source provides name length, postal prefix, and some missing product attributes | Do not invent source names/full addresses; keep nulls and original strings, with English analytical labels |
| Every category has an English translation | 610 products lack a category; 2 nonblank category keys lack translations | Create category keys from the union of product/translation data; keep English translation nullable |
| Previous benchmarks apply | Imported data distribution and query questions differ | Run a new experiment only after import; retain old results as unrelated history |

## Target domains and boundaries

### Historical Olist domain

Create an `olist` Django app with read-only historical customer, product, category, seller, order, item, and payment models, plus dataset-snapshot/import-run metadata. Delivery facts remain on the source order: the dataset does not provide per-seller shipment tracking or an item-level delivery timeline. Do not synthesize shipment records or tracking codes from order-level dates.

Preserve source identifiers as strings, without interpreting anonymized hashes as Django user IDs or UUIDs. Store original statuses, prices, freight, payment types, and source location/category values. Preserve source timestamp text and a validated timezone-free representation for analysis. If native PostgreSQL `timestamp without time zone` support needs a custom Django field, keep it small and test round trips; do not let `USE_TZ=True` silently reinterpret the source. Use a source-local calendar for initial month/date reports and disclose that its time zone is unspecified. A later UTC conversion requires an explicit assumption and DST policy.

Historical routes will be under `/api/olist/`, with paginated administrative reads and reports. No customer may claim a historical order by knowing an anonymized source identifier. HTTP write operations on historical resources are rejected even for administrators. Imports use a dedicated management command and database role; the API role should have only SELECT privileges on historical tables. Schema ownership/migrations and importer writes use separate credentials in the isolated environment. No historical mutation via simulation services is permitted.

### Simulated operational domain

Retain the existing account/profile, order-lifecycle, atomic reservation, stock ledger, and simulated payment concepts. Add explicitly simulated sellers and seller/product offers. Products describe items; offers contain fictional current price/availability. Stock, movement history, duplicate-line rules, cancellation headroom, and reservation/release uniqueness move from product to **offer** identity.

An order may contain offers from several sellers. Its items snapshot product identity/name, seller identity/label, offer identity, unit price, and positive quantity. Offer seller/product associations are immutable. Simulated item uniqueness is `(order, offer)`, allowing the same product from different sellers. Preserve the existing pending-only cancellation rule and restore every seller offer exactly once. An initial simulation supports order-wide processing, not independently paid/cancelled suborders or real seller fulfillment.

Use one lock order: an existing order first when needed; then all affected sellers by ID; then products by ID; then offers by ID; then stock rows by offer ID. Re-read activation and prices after locks. Seller/product/offer edits and inventory services follow the same order, never reverse it. Listing uniqueness is `(seller, product)`. Seller, product, and offer deactivation block new purchases but not pending-order cancellation. Cross-seller rollback and controlled last-unit races must be tested at offer level.

Only fictional `example.com` login accounts are created. All inventory, stock movements, current offer prices, new payments, seller identities used in the simulation, and operational delivery events are labeled simulated. An optional later demo projection may retain a nullable reference to a historical product/seller for provenance, but it must create a clearly separate simulated object. It must not copy an observed historical price into a field described as today's real price or associate a source customer identity with a login.

Keep history and simulation in separate tables, route namespaces, serializers, permissions, and report entry points. Responses/examples must expose `data_origin` as `OLIST_HISTORICAL` or `SIMULATED_API`, and payment representations must separately identify recorded source payment rows versus simulated approvals. Never union their sales metrics by default.

## Import contract

The future `import_olist` command will be implemented after model review, not in this delivery. Its responsibilities are:

1. Require an explicitly enabled, isolated target database with its own Compose project/volume and a confirmed expected database name. Do not reuse or reset the legacy database. Do not run `flush`, truncate existing domains, or remove existing volumes.
2. Read local CSVs/ZIP and a locked manifest. Record source URL, publisher version labels, retrieval date, archive/member SHA-256, schema/mapping version, and per-file row counts. Verify hashes, headers, encoding, required files, types, finite nonnegative source money, integer sequences, source keys, and FKs. Preserve postal prefixes as five-character text, including leading zeros.
3. Stage and validate before publication. Resolve customers/categories/products/sellers before orders, then items and payments. Missing categories/attributes are allowed; missing required parent identities are quarantined, never fabricated.
4. Classify every input row as imported, unchanged/skipped, duplicate-input, or rejected. Report inconsistency flags separately because a structurally valid row can be imported with several issues; issue totals are not additional row totals. Record both proposed and actually committed counts.
5. Preserve representable source inconsistencies: missing lifecycle dates, unexpected chronology/status combinations, zero payment/installment values, untranslated categories, missing item/payment sides, and reconciliation differences. Never manufacture a missing approval, payment, address, seller, or stock movement to make a row pass simulation rules.
6. Default to no publication if structural rejection/ambiguous duplicate keys exist. Emit a report with rejected file/row/source key/reason and zero committed domain rows. Partial acceptance, if implemented later, requires an explicit option and separate documented counts. Dry-run must not write domain or import-state tables.
7. Serialize import attempts with a database-scoped import lock. Publish valid historical rows and their completed snapshot marker atomically. Keep attempt/failure metadata durable outside a failed data transaction; readers see only completed snapshots.
8. Support one immutable source snapshot per isolated database initially. A rerun with the same complete manifest and mapping version is a verified no-op with skipped counts. Verify persisted keys/content/counts as well as the manifest before declaring a no-op; a partial/corrupted target is an error, not success. Any different snapshot or conflicting target is refused and requires a fresh isolated database. Unique source keys provide a second line of duplicate defense; do not hide conflicts with `ignore_conflicts=True`.
9. Produce a machine-readable JSON report and an English summary with imported, skipped, rejected, inconsistent-row and issue counts, parent failures, reconciliation deltas, hashes, target identity, version/mapping, duration, and final status. Do not include credentials or review free text. CLI failures return nonzero; an anomaly-bearing successful import is visibly qualified.
10. Prove the command with tiny hand-built test fixtures, deliberate failures, repeated and concurrent imports, rollback assertions, and a full isolated import matching the inspected source totals. Publish actual commands/results before stage approval.

Reviews and raw geolocation are explicitly deferred from the initial import. The archive is inspected and fingerprinted in full, but these CSVs are not silently counted as imported. A future review import must account for repeated review IDs/multiple reviews per order; a geolocation import must profile and aggregate repeated postal prefixes before joins. No marketing dataset or identity re-identification is included.

## SQL analysis contract

Every report documents source snapshot, grain, date basis, included statuses, null/empty behavior, and quality exclusions. Initial default sales scope is source `delivered` orders; label results as **historical delivered-order merchandise value**, freight, or recorded payment value, not audited net revenue, profit, settled cash, or seller payout. Alternative status scopes must be explicit. Delivery-incomplete rows can still contribute merchandise facts; they are excluded only from timing metrics requiring their missing dates. Repeat behavior is observed only within this snapshot/window, not a customer's lifetime. Partial boundary months and missing facts limit comparisons; do not present them as complete current market activity.

| Question | SQL concepts and grain | Safeguard |
| --- | --- | --- |
| Order detail with customer, product category, and seller | INNER JOIN, one row per source item | Keep source line IDs; present status and historical price/freight |
| Orders/customers with and without item/payment facts | LEFT JOIN, preaggregated order facts, COALESCE plus explicit missing-side flags | Do not confuse absent payment with recorded zero; group customers at the stated identity grain |
| Monthly merchandise, freight, and recorded payments | CTEs, GROUP BY, aggregates, purchase-month buckets | Aggregate items and payments separately to one row per order before joining; no installment multiplication |
| Repeat-customer rates and spending | Customer/order CTEs, COUNT DISTINCT, HAVING, DENSE_RANK | Group by `customer_unique_id`; define repeat as at least two eligible delivered orders in the stated observation window |
| Product-category and seller rankings | Item aggregates, HAVING, ROW_NUMBER/DENSE_RANK | Attribute item prices/freight to their source seller; do not allocate order payments as observed seller proceeds |
| Monthly running merchandise totals | Monthly CTE, zero-filled calendar, SUM OVER with explicit ROWS frame | Fixed requested interval and deterministic ordering; empty months are zero |
| Delivery timeliness by month/state and associated seller | Date expressions, FILTER aggregates, CTE/window rankings | Use delivered orders with valid dates; compare delivery calendar date with estimated calendar date; publish denominators/exclusions |
| Payment/item reconciliation | Separate item/payment CTEs, LEFT JOIN, decimal differences | Show missing sides and observed differences; no manufactured adjustment |

Seller-associated delivery metrics count distinct `(order, seller)` pairs and describe order-level outcomes for orders containing that seller. They are not measured seller-specific shipment delivery times. Do not attribute an entire order's payments or merchandise total to each seller. SQL tests must include multiple items and multiple payments on the same order; the inspected source contains 275 such orders.

The new index experiment should target a realistic historical report, such as delivered orders in a fixed purchase-time interval with deterministic sorting. Select the actual query/index only after import and inspect existing indexes first. Freeze identical SQL, parameters, snapshot/data fingerprints, and ordered result hashes; retain all constraints; update statistics; use warm-ups, at least seven measured runs per phase, and a repeated baseline control. Capture full `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` plans, individual times/medians, settings, database/runtime versions, index bytes, buffer activity, and cache limits. Sequential scans or no improvement are valid outcomes. Do not reuse the old fictional-data measurements.

Use the full imported snapshot in an isolated benchmark clone to preserve its real distribution. Do not inflate rows or add fictional sales while calling the result real Olist evidence. The operational demo stays in separately labeled tables/environments and is never the historical benchmark dataset.

## Incremental delivery and checkpoints

| Delivery | Scope | Required evidence before the user's review |
| --- | --- | --- |
| Adaptation plan, current delivery | Inspect implementation and source, document conflicts, source/license, dictionary, ER design, SQL/import contracts | Executed archive profile, reproducibility checks, independent review; no database import or application claims |
| Stage 2 | Selectively port existing setup; isolated Compose/PostgreSQL roles; historical models and seller-offer simulation models; constraints/migrations; schema export | Runtime versions, PostgreSQL checks, migration/restore consistency, FK/uniqueness and source-time round-trip tests |
| Stage 3 | Repeatable Olist import and report; read-only historical APIs; adapt account/product/customer APIs and permissions | Full import counts, anomaly preservation, failure/no-op/concurrent-import tests, auth/owner/admin/read-only tests, actual source-ID examples |
| Stage 4 | Multi-seller simulated orders, offer inventory/ledger, lifecycle/payment adaptation | Cross-seller atomicity, headroom, snapshots, cancellation, offer-level controlled PostgreSQL concurrency; explicit simulation labels |
| Stage 5 | Executed Olist SQL portfolio and new index experiment | SQL fixtures and source results; preserved plans, samples, medians, equivalence, storage/cache limitations |
| Stage 6 | Final English README, ER, dictionary, OpenAPI, Docker/import guides, curl examples and portfolio narrative | Reproduced workflows, complete relevant tests, attribution and limitations; no affiliation claims |

Tests accompany each implementation delivery. Each stage receives independent review; material findings are corrected and rechecked, then English commits are published. Stop for the user's technical review before the next stage. The request to continue using Olist establishes direction; it does not erase these explicit review checkpoints.

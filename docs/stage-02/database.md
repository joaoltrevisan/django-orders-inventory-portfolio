# Stage 2: implemented relational model and integrity boundaries

The PostgreSQL schema now implements the historical and simulated domains from the approved Olist plan. The [ER diagram](../olist/data-model.md) highlights the relationships; [schema.sql](../../sql/schema.sql) is the complete migration-generated export, including Django authentication/framework tables omitted from that diagram.

## Reused implementation and adaptations

Selectively reused the existing application's custom user/manager, timestamp base, numeric limits/strict integer field, order snapshot/lifecycle checks, and inventory movement constraints. All copied meaningful comments, labels, and messages were adapted to English. The legacy repository's migrations were **not** replayed against its database: this independent database has fresh initial migrations reflecting the reviewed Olist design.

Current price was removed from simulated `Product`. `Seller` and `Offer` were added, with unique `(seller, product)` and positive finite `simulated_price`. Stock's unique FK now targets an offer. Simulated items use unique `(order, offer)` and preserve product SKU/name, seller label, quantity, and unit price. Movement uniqueness is `(order, offer, movement_type)` for reservations/releases. The previous speculative performance indexes were not copied; Stage 5 must measure its own imported-data candidates.

An offer's seller/product associations are protected by the `offer_identity_immutable` PostgreSQL trigger. It rejects changes from ORM saves, bulk updates, and raw SQL using `IS DISTINCT FROM`. Price/activation updates remain possible. The migration includes reverse SQL for the trigger/function; these definitions are included in schema restoration comparison. Operational stock locking and transactional services remain Stage 4 work; model checks alone do not prevent overselling.

## Historical relationships and source representation

| Object | Implemented guarantee |
| --- | --- |
| Dataset snapshot | Unique non-null singleton column checked equal to 1; unique valid SHA-256; checked publication vocabulary; one snapshot per database |
| Import run/issue | Failed attempts can have no snapshot; checked statuses/severity; source row number nullable or positive; durable import transaction/reporting behavior remains Stage 3 |
| Historical customer | Unique 32-character source customer ID; indexed nonunique repeat identity; five-character textual postal prefix; no authentication FK |
| Category/product | Unique source category/product keys; untranslated category English label and absent category/measurements remain nullable; no current price, commercial name, or inventory field on historical product |
| Historical seller | Unique source seller ID, textual postal prefix/location; no operational account or live offer inferred |
| Historical order | Unique source order ID, protected customer/snapshot FKs, original nonblank status and nullable source dates; no operational lifecycle mapping |
| Historical item | Unique `(order, source_order_item_id)`, product and seller FKs, positive source sequence, nonnegative finite historical price/freight; repeated products/sellers are allowed |
| Historical payment | Unique `(order, payment_sequential)`, positive sequence, nonnegative installments/value; zero records are retained; no fabricated per-payment approval time |

Source money uses `numeric(16,2)` with explicit nonnegative finite upper bounds. Simulation prices/item snapshots use `numeric(10,2)` and require positivity. PostgreSQL numeric `NaN` is explicitly covered by finite upper-bound checks; tests exercise negative, nonfinite, and excessive raw SQL values. Python money uses `Decimal`.

FK/unique/check constraints are real PostgreSQL objects. Django `PROTECT` prevents ORM deletion of referenced history; database FKs independently reject dangling references. Deferred FK tests force constraint evaluation before declaring a failure covered. The singleton snapshot restriction makes cross-snapshot links impossible within this initial design; supporting multiple snapshots would require a new explicit relationship/constraint design.

## Preserving source clocks under USE_TZ

`olist.fields.SourceDateTimeField` uses native `timestamp without time zone` and deliberately subclasses plain Django `Field`, not `DateTimeField`. It accepts naive datetime values or exact `YYYY-MM-DD HH:MM:SS` text, rejects aware values/fractional seconds, and bypasses Django's implicit timezone conversion. All five historical order timestamps and the item shipping deadline retain matching raw-text fields; missing optional source times remain null with blank raw text.

Source times are not verified UTC instants. Date parsing and raw/parsed consistency will be validated by the importer. This schema does not claim that arbitrary privileged SQL can never introduce a raw/parsed mismatch. Ordinary operational timestamps and import metadata continue to use aware timestamps.

Inherited ORM `__year` and date truncation are intentionally unavailable on the custom field: Django can inject `AT TIME ZONE` for standard date fields. Source reports must use explicitly verified timezone-free PostgreSQL expressions, such as `date_trunc('month', purchased_at_source)`. Exact/range comparisons and ordering work. Tests verify native column type and round trips at month boundaries and Brazilian DST-adjacent source values while both active Django and database time zones are `America/Sao_Paulo`.

## Constraints versus services and privileges

Database checks cover local ranges/signs, keys, FKs, simulation status/timestamp consistency, and immutable offer identity. They do not prove a nonempty operational order, server-calculated total, exact item/movement correspondence, cancellation headroom, permitted previous-to-next transitions, or ledger balance. These need the reviewed transactional services and controlled concurrency tests in Stage 4. Current model fixtures test relational capabilities and intentionally do not claim that creating rows directly runs a valid operational purchase workflow.

Historical timestamps/status exceptions, multiple payments, orders without item/payment rows, zero payment values, and missing categories are representable. Do not repair these to satisfy simulation checks. API database credentials have SELECT only on historical tables. The importer can insert source facts and update limited import/publication metadata, not rewrite or delete history. The owner remains privileged for migrations; this project does not claim tamper-proof history against schema owners or arbitrary privileged SQL.

The [setup guide](setup.md) documents actual role/grant commands. The schema-only export omits ownership/ACLs: portable structure restoration and runtime permission verification are separate checks. Neither a diagram nor a schema-only dump by itself proves the security boundary.

## Index baseline

Only correctness/relationship baseline indexes are present: primary keys, unique identities, case-insensitive email expression, unique one-to-one FKs, item/payment/offer composite keys, conditional movement uniqueness, Django FK indexes, and the repeat-customer identity index. Some database-created prefix lookup indexes support Django's unique varchar fields; inspect the actual export before proposing duplicates. No historical query optimization gain is claimed before import and measured EXPLAIN evidence.

The exported schema currently has 28 tables and 20 applied migrations in its source database. A schema-only restore contains zero migration-history rows, as intended. Actual structural comparison, test, runtime, and role evidence is linked in this stage's verification record.

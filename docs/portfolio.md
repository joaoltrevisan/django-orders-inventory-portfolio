# Order and Inventory Management Service for Olist

**Backend service by João Trevisan** addressing multi-seller order and inventory workflows in Olist's marketplace context. The implementation combines a transactional operational API with separate historical marketplace analysis, using Python, Django REST Framework and PostgreSQL.

## Problem and delivered behavior

A multi-seller basket must either reserve every selected offer or fail completely. Catalog edits must preserve what the buyer purchased; cancellation must restore quantities once; customers must not access other customers' orders. Marketplace analysis must retain the meaning of source identities, statuses and monetary facts rather than multiplying item/payment rows or inventing current inventory from old sales.

The service delivers JWT registration/login and scoped profiles/orders, administrative catalog/customer/inventory/processing, immutable purchase snapshots, optional customer-scoped idempotent creation, fixed payment deadlines, audited administrative expiry and optional periodic execution with observed backlog, plus private logical recovery verified against row/schema fingerprints, stock movement history, controlled state transitions and twelve parameterized SQL reports. PostgreSQL constraints protect local integrity while services coordinate cross-table invariants with atomic transactions and consistently ordered locks. [Architecture](architecture.md) and [ER diagrams](olist/data-model.md) explain these decisions.

## Technical evidence to inspect

| Competency | Concrete implementation / evidence |
| --- | --- |
| Backend design | Clear accounts/catalog/inventory/orders/olist modules; DRF validation, permissions, pagination and [OpenAPI](../reports/recovery/local/openapi.json) |
| Relational modeling | Multi-seller historical item relationships and operational seller/product offers; PK/FK/unique/check constraints; migration-consistent [SQL export](../sql/schema.sql) |
| Integrity/concurrency | Atomic offer reservations, consistent lock hierarchy, server totals/snapshots, cancellation once; separate-connection controlled PostgreSQL tests |
| Data engineering | Locked-source repeatable importer with field/relationship fingerprints, duplicate/no-op protection, atomic publication and retained anomaly reports |
| SQL | INNER/LEFT JOIN, GROUP BY/HAVING, aggregate CTEs, SUM OVER, DENSE_RANK and ROW_NUMBER with explicit business grain/status/null definitions |
| Measured optimization | Identical SQL/data, statistics refresh, warm-ups, repeated samples/control, 30 actual JSON plans, buffers/storage and result equivalence |
| Reproducibility/review | Docker/Compose roles and independent environments, executed PostgreSQL suites with [current evidence](recovery/verification.md), real curl workflows and independent review records |

The accepted historical snapshot includes **99,441 orders, 112,650 item rows, 103,886 payment records, 32,951 products and 3,095 sellers**. Separate aggregation avoids item/payment join multiplication. Repeat-customer grouping uses `customer_unique_id`, while joins use `customer_id`. Under the documented delivered-order cohort, executed SQL identified **2,801 repeating identities among 93,358 eligible identities (3.00%)**. These are observed source/window measures, not current market or lifetime-customer claims.

The measured delivered-order page changed from a parallel order-table scan/sort to an index-only ordered scan. Median server execution was **5.356 ms baseline → 0.080 ms indexed**, with **5.135 ms control** after index removal and **7.90 MiB** index storage. Seven samples per phase and all plans are in the [performance report](stage-05/index-experiment.md). Cache was warm; the result applies to that fixed query, and the candidate was removed rather than adopted as a production migration. This dated Stage 5 experiment was not rerun during documentation consolidation.

## Suggested technical walkthrough

1. Follow [operational setup](getting-started.md#path-a-operational-demonstration), which needs no historical archive. Inspect example.com accounts, three seller offers and five lifecycle states.
2. Run the guarded real-curl workflow on a fresh seeded target. Observe a 91.80 multi-seller purchase, unchanged purchase snapshots after repricing, cancellation restoration once, a new-price 100.00 purchase, simulated processing and insufficient-stock rollback.
3. Read the [test guide](testing.md), especially separate-connection last-unit contention and the difference between database constraints and application invariants.
4. Follow [historical analysis setup](getting-started.md#path-b-historical-import-sql-and-index-analysis), inspect the import report and execute the [SQL portfolio](stage-05/sql-portfolio.md).
5. Inspect the raw before/after/control plans and cache/storage trade-offs, then discuss what further workload evidence would justify an index migration.

Final execution results and the initially failed/corrected curl example are retained in [Stage 6 verification](stage-06/verification.md). Source anomalies are disclosed rather than repaired to produce cleaner metrics. No fabricated performance measurements or unexecuted tests are presented as evidence.

[Recovery evidence](recovery/verification.md) separately demonstrates actual isolated restoration of operational data and the full historical snapshot, retaining each captured migration version rather than treating an old backup as an automatic application upgrade.

## Scope and provenance

This independently developed service uses Olist's publicly released anonymized dataset for historical analysis. It does not imply employment, a commissioned contract, partnership, endorsement or internal-system access. Technical source identity, version ambiguity, attribution and **CC BY-NC-SA 4.0** requirements are in [THIRD_PARTY_DATA.md](../THIRD_PARTY_DATA.md).

Authentication, current prices/offers, inventory, new payments and operational fulfillment are explicitly simulated and separate from historical facts. The service is locally reproducible, not publicly deployed or production-certified. Optional keyed creation retries are implemented with transaction serialization and preserved snapshots. Production supervision/alerts, real integrations and deployment hardening remain prioritized [future improvements](limitations.md).

# Order and Inventory Management Service for Olist


[![PostgreSQL verification](https://github.com/joaoltrevisan/django-orders-inventory-portfolio/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/joaoltrevisan/django-orders-inventory-portfolio/actions/workflows/ci.yml)


A backend service by **João Trevisan** designed to address order and inventory management needs in Olist's marketplace context. The service combines multi-seller ordering, seller offers, stock control, customer access and sales analytics, with relational integrity and transactional consistency at its core.


Built with **Python, Django REST Framework, PostgreSQL, JWT and Docker Compose**. Repository: [joaoltrevisan/django-orders-inventory-portfolio](https://github.com/joaoltrevisan/django-orders-inventory-portfolio).


## What the service delivers


- Customer registration/login/refresh, self-only profiles/orders and administrative customer/catalog/processing permissions.
- Orders with multiple sellers, server-calculated decimal totals and immutable purchase-price/name snapshots.
- Atomic per-offer stock deduction, actor-attributed movement history, full insufficient-stock rollback and cancellation restoration exactly once.
- Optional customer-scoped creation keys with atomic retry/replay, content conflicts and coherent current-state responses.
- Fixed new-order payment deadlines and an administrator-attributed expiry command that restores stock once.
- An optional periodic expiry worker with graceful shutdown, fresh authorization, sanitized cycle logs and observed backlog metrics.
- Private PostgreSQL logical recovery drills with shared-snapshot row hashes, isolated restores, schema equality and next-ID safety.
- A constrained order lifecycle with consistently ordered PostgreSQL locks and controlled separate-connection concurrency tests.
- A repeatable validated historical import and twelve SQL reports covering sales, repeat customers, categories, sellers, delivery and financial completeness.
- Independent demonstration/analysis databases, migration-consistent SQL export, OpenAPI and actual query-optimization evidence.


## Start and explore


Follow the [execution guide](docs/getting-started.md). **Path A** runs a small operational demo without downloading historical data; **Path B** imports the locked Olist snapshot and reproduces SQL analysis in a different database. Existing environments and credentials are preserved; generators refuse overwrite and commands never reset populated data automatically.


For a fresh operational demo, generate its private configuration and build the image:


```bash
python3 scripts/create_analysis_env.py demo
mkdir -p .local/analysis-reports .local/import-reports
docker compose -p olist-demo --env-file .local/analysis/demo.env build app
```


Continue with the guide's migration/grant/seed/start commands. Skip configuration generation if that file already exists. The demo uses loopback-only services; PostgreSQL is not published. Use the ports shown in the generated configuration and the execution guide. Health returns `{"status":"ok","stage":6}`. API version **1.4.0** denotes this completed scope, not production readiness.


The guarded [real-curl workflow](scripts/verify_curl.py) exercises registration, JWT, keyed creation/replay/conflicts, catalog, a multi-seller purchase, repricing snapshots, repeated cancellation, simulated processing, stock rollback and permissions on a confirmed fresh seeded demo. It keeps credentials off argv and out of evidence. [API examples](docs/api.md) cover individual requests and token handling.


## Verified results


The six planned stages and the subsequent authorized extensions are complete. API **1.4.0** passed **221 PostgreSQL tests locally and on GitHub Actions**, with **75 database-role checks**, strict OpenAPI validation for **38 paths**, and migration/export/restore verification of **28 tables / 22 migrations**. The final fresh-environment workflow passed **50 real curl requests**. See the [delivery closeout](docs/delivery.md) for acceptance coverage, exact evidence, independent review and remaining deployment limits.


Private recovery drills also verified all 28 table fingerprints, schema and next-ID safety for both an operational source and the **99,441-order historical benchmark**, preserving each source's captured migration version. Backups remain private. The [recovery verification](docs/recovery/verification.md) retains the complete local/hosted results; older release counts remain dated in the [test guide](docs/testing.md#release-evidence).


The imported historical snapshot contains **99,441 orders, 112,650 item rows, 103,886 payment records, 32,951 products and 3,095 sellers**. Import accepted **451,535 source rows / 451,537 entities**, rejected none and retained **3,739 warning issues across 3,116 rows** without repairing the source. Repeat identities use `customer_unique_id`; order joins use `customer_id`. Delivered-order SQL identified **2,801 repeat identities among 93,358 eligible identities (3.00%)** in the defined source window.


One delivered-order page query was measured in Stage 5 with identical SQL/data, refreshed statistics, three warm-ups and seven measured runs per phase. Median server execution: **5.356 ms baseline, 0.080 ms indexed, 5.135 ms control after removal**. The temporary index occupied **7.90 MiB**. All **30 actual JSON plans**, individual times, buffers, result hashes and storage measurements remain in the [experiment report](docs/stage-05/index-experiment.md). These are warm-cache results for that query; the candidate was removed and is not a production migration. Documentation consolidation did not rerun this dated experiment.


## Documentation and evidence


| Material | Contents |
| --- | --- |
| [Delivery closeout](docs/delivery.md) | Completed requirements, final checks, review and scope boundary |
| [Execution guide](docs/getting-started.md) | Docker, two isolated data paths, credentials, import/seed and real-curl commands |
| [Architecture](docs/architecture.md) | Modules, transactions, lock hierarchy, constraints versus service invariants, roles and trade-offs |
| [ER diagrams](docs/olist/data-model.md) / [source dictionary](docs/olist/data-dictionary.md) | Relationships, keys, historical identifiers, source clocks and actual field meanings |
| [API reference](docs/api.md) / [OpenAPI](reports/recovery/local/openapi.json) | Authentication, permissions, all workflows, filters, response/error semantics |

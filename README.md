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

Continue with the guide's migration/grant/seed/start commands. Skip configuration generation if that file already exists. The demo binds to loopback port **18022**, the existing service to **18020**; PostgreSQL is not published. Health returns `{"status":"ok","stage":6}`. API version **1.3.0** denotes this completed scope, not production readiness.

The guarded [real-curl workflow](scripts/verify_curl.py) exercises registration, JWT, keyed creation/replay/conflicts, catalog, a multi-seller purchase, repricing snapshots, repeated cancellation, simulated processing, stock rollback and permissions on a confirmed fresh seeded demo. It keeps credentials off argv and out of evidence. [API examples](docs/api.md) cover individual requests and token handling.

## Verified results

The Stage 6 suite passed **130 PostgreSQL tests**. The continuous-integration extension passed **137 PostgreSQL tests both locally and on GitHub Actions**; [CI verification](docs/ci/verification.md) records actual runs and their artifacts. **39 real curl requests** passed on a separate seeded review environment. Strict OpenAPI validation passed for **38 paths**; SQL export/restore verification confirmed **28 tables and 20 migrations**. The [final verification](docs/stage-06/verification.md) records commands, outcomes, the corrected initial curl example, environment isolation and remaining limits.

API 1.1.0 passed **157 PostgreSQL tests locally and on GitHub Actions**, including **20 creation-key tests and five new controlled contention scenarios**. The extended workflow passed **50 real curl requests**. Strict OpenAPI covers **38 paths**; schema export/restoration confirms **28 tables and 21 migrations**. All 23 existing domain-table row counts/hashes matched across the additive migration in an isolated review database. See [creation-key verification](docs/idempotency/verification.md) for commands, artifacts, independent review and hosted CI status. Earlier Stage 6/CI results above remain dated evidence.

API 1.2.0 passed **184 PostgreSQL tests locally and on GitHub Actions**, including 27 new expiry/verification tests and eight new coordinated concurrency scenarios. General HTTP verification passed **50 real curl requests**; expiry verification passed **16 more requests and three CLI checks**. The additive migration preserved all 23 captured domain-table hashes and five legacy NULL pairs. Current schema/OpenAPI: **28 tables, 22 migrations, API 1.2.0 / 38 paths**. See [expiry verification](docs/reservations/verification.md) for actual commands, corrections, evidence and hosted status.

API 1.3.0 passed **204 PostgreSQL tests locally**, including 20 new worker/safety tests. Actual container verification observed two finite cycles, two graceful SIGTERM sessions and a single stock release across repeated execution. Default Compose retains five services; the optional overlay adds only the worker. Schema remains **28 tables / 22 migrations**, with **38 OpenAPI paths**. [Worker verification](docs/worker/verification.md) records exact commands, evidence, independent review and hosted status.

The imported historical snapshot contains **99,441 orders, 112,650 item rows, 103,886 payment records, 32,951 products and 3,095 sellers**. Import accepted **451,535 source rows / 451,537 entities**, rejected none and retained **3,739 warning issues across 3,116 rows** without repairing the source. Repeat identities use `customer_unique_id`; order joins use `customer_id`. Delivered-order SQL identified **2,801 repeat identities among 93,358 eligible identities (3.00%)** in the defined source window.

One delivered-order page query was measured in Stage 5 with identical SQL/data, refreshed statistics, three warm-ups and seven measured runs per phase. Median server execution: **5.356 ms baseline, 0.080 ms indexed, 5.135 ms control after removal**. The temporary index occupied **7.90 MiB**. All **30 actual JSON plans**, individual times, buffers, result hashes and storage measurements remain in the [experiment report](docs/stage-05/index-experiment.md). These are warm-cache results for that query; the candidate was removed and is not a production migration. Documentation consolidation did not rerun this dated experiment.

## Documentation and evidence

| Material | Contents |
| --- | --- |
| [Execution guide](docs/getting-started.md) | Docker, two isolated data paths, credentials, import/seed and real-curl commands |
| [Architecture](docs/architecture.md) | Modules, transactions, lock hierarchy, constraints versus service invariants, roles and trade-offs |
| [ER diagrams](docs/olist/data-model.md) / [source dictionary](docs/olist/data-dictionary.md) | Relationships, keys, historical identifiers, source clocks and actual field meanings |
| [API reference](docs/api.md) / [OpenAPI](reports/worker/local/openapi.json) | Authentication, permissions, all workflows, filters, response/error semantics |
| [SQL portfolio](docs/stage-05/sql-portfolio.md) | Twelve business questions with JOIN/aggregation/CTE/window SQL, grains, statuses and NULL rules |
| [Index analysis](docs/stage-05/index-experiment.md) | Hypothesis, individual measurements/medians, raw plans, buffers/storage and limitations |
| [Optional expiry worker](docs/worker/operations.md) / [verification](docs/worker/verification.md) | Opt-in scheduling, shutdown/retry policy, observational backlog and actual container evidence |
| [Reservation expiry](docs/reservations/design.md) / [verification](docs/reservations/verification.md) | Deadline policy, explicit audited expiry, partial batches and controlled concurrency |
| [Creation idempotency](docs/idempotency/design.md) / [verification](docs/idempotency/verification.md) | Optional key contract, locking, additive migration, HTTP and test evidence |
| [Test guide](docs/testing.md) | PostgreSQL suite, controlled concurrency, schema restoration and actual versus illustrative HTTP evidence |
| [Continuous integration](docs/ci.md) | GitHub Actions and a shared disposable local/hosted PostgreSQL verification pipeline |
| [Technical presentation](docs/portfolio.md) | Service problem, delivered behavior, implementation evidence and walkthrough |
| [Security and limitations](docs/limitations.md) | Implemented controls, functional/deployment limits and prioritized future work |
| [Final verification](docs/stage-06/verification.md), [review](docs/stage-06/review.md), [file inventory](docs/stage-06/changes.md) | Actual commands/results, independent findings and every changed/created file |
| [SQL schema](sql/schema.sql) / [migrations](olist/migrations/0001_initial.py) | Reproducible structural export and representative source-model migration; normal setup uses all migrations |
| [Data attribution](THIRD_PARTY_DATA.md) | Source version/hash identity, transformations and license requirements |

Stage records under `docs/stage-01` through `docs/stage-06` preserve the incremental work and its actual evidence. Older stage guides describe those deliveries, not the current feature set. All six planned stages are implemented; final technical review remains the user's checkpoint. [Review process](docs/review-process.md) defines the independent-review workflow.

## Runtime and data boundaries

Actual container versions: **Python 3.12.15, Django 5.2.18 LTS, DRF 3.18.3, PostgreSQL 17.11, SimpleJWT 5.5.1 and psycopg 3.3.6**. Dependencies are pinned in [requirements.lock](requirements.lock); [current runtime evidence](reports/worker/local/runtime.json) records Python, package, PostgreSQL and architecture versions.

Historical tables and administrator-only `/api/olist/` routes preserve source prices/statuses and recorded payments. They never become current stock, offers, login accounts or payment processing. The operational domain uses fictional `example.com` identities and explicitly simulated accounts, seller offers/prices, stock movements, new payments and delivery actions. Item and payment facts are aggregated separately to prevent double-counting. Source timestamps have no verified timezone; operational events use aware UTC.

Historical analysis uses the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), identified by locked archive/member hashes and attributed under **CC BY-NC-SA 4.0**. See [THIRD_PARTY_DATA.md](THIRD_PARTY_DATA.md) for the reported version ambiguity, transformations and obligations. This independently developed project does not claim employment, a commissioned contract, partnership, endorsement or access to Olist's internal systems. Raw data, env files, credentials, tokens and full row-level issue reports stay outside Git. Local Compose execution is not public production hosting.

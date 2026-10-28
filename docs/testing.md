# Tests and reproducible evidence

[Continuous integration](ci.md) provides a disposable equivalent on GitHub Actions and locally, with its own database, volume, image and credentials. The commands below remain useful for testing an intentionally configured development environment.

Build the current image, initialize the primary PostgreSQL schema and apply role grants using the [execution guide](getting-started.md). No Olist download is required for automated tests: tiny explicitly fictional source fixtures exercise import/report semantics, while actual source analysis has separate evidence.

```bash
docker compose run --rm --entrypoint python app -m pip check
docker compose run --rm --entrypoint ruff app check --no-cache .
docker compose run --rm --entrypoint ruff app format --check --no-cache .
docker compose run --rm migrate check
docker compose run --rm migrate makemigrations --check --dry-run
docker compose run --rm migrate migrate --check
docker compose run --rm tests
```

The current API **1.4.0** suite passed **221 tests** against PostgreSQL locally and on GitHub Actions. See [current recovery verification](recovery/verification.md) and the [delivery closeout](delivery.md) for executed commands and results. The `tests` service uses `olist_test`, creates/destroys `test_olist_case_study` and does not flush the application database. Run suites serially against a given target; concurrent suite invocations can collide on Django's test database name. Do not substitute application/owner credentials for the test service.

## Release evidence

| Delivery | Executed PostgreSQL tests | Dated verification |
| --- | ---: | --- |
| Stage 6 | 130 | [Original six-stage delivery](stage-06/verification.md) |
| CI extension | 137 | [Local and hosted CI](ci/verification.md) |
| API 1.1.0 | 157 | [Creation keys](idempotency/verification.md) |
| API 1.2.0 | 184 | [Reservation expiry](reservations/verification.md) |
| API 1.3.0 | 204 | [Optional expiry worker](worker/verification.md) |
| API 1.4.0 | 221 | [Private logical recovery](recovery/verification.md) |

To retain all seven command arrays, stdout/stderr and exit codes with completed test count/runtime:

```bash
python3 scripts/verify_stage2.py --output .local/analysis-reports/checks-new.json
```

The helper's historical filename is retained; it runs the **current complete suite**, not only Stage 2 tests. It refuses an existing output filename and stops on failed commands. [Final verification](stage-06/verification.md) links the actual run, including corrections and limits.

## Coverage and interpretation

| Area | Important assertions |
| --- | --- |
| Authentication/accounts | Atomic registration, Django hashing, password validation, normalized email, JWT expiration/types/refresh, current account/password/role revocation, owner/admin boundaries |
| Catalog/database | Positive finite decimals, strict integer inputs, composite keys, immutable offer identity, protected historical references, timezone-free source round trips |
| Orders/inventory | Server totals and snapshots, multi-seller writes, full insufficient-stock rollback, ledger balance, capacity/headroom, cancellation repetition, invalid transitions, coherent payment/shipment responses |
| Concurrency | 28 controlled operational scenarios with separate PostgreSQL connections/backend PIDs and coordination events: 25 observed lock waits and three verified SKIP LOCKED schedules; includes last-unit races, reversed multi-offer input, cancellation/payment, pricing and adjustments |
| Creation keys | Canonical equivalence, scoped ownership/current authorization, null-safe hash constraints, conflict/replay status and headers, unchanged legacy creation, rollback reuse, edited catalog/current lifecycle replay; five controlled advisory/order-lock races |
| Reservation expiry | Exact/boundary/legacy deadlines, explicit audited release, partial batches, guard/role checks, full rollback and eight separate-connection races (five observed waits, three verified SKIP LOCKED schedules) |
| Import | Locked identity/content, structural failures/duplicates, anomaly preservation, atomic failure, no-op/corruption, concurrent import lock, durable sanitized attempt metadata |
| SQL reports | Multiple item/payment facts without multiplication, repeat identity, canceled/empty intervals, HAVING/ranking ties, missing versus zero, calendar windows, delivery eligibility and seller association deduplication |
| Analysis/verification tools | Demo seed refusal/rollback, benchmark cleanup after injected failure, preexisting index preservation, wrong-target refusal and curl write-target/loopback guards |

Concurrency tests rely on controlled coordination and observed database locks rather than only arbitrary delays. Passing observed schedules does not prove every possible production schedule or deadlock absence. Miniature benchmark protocol tests use real PostgreSQL DDL/EXPLAIN with a test-only mocked isolated-target guard; their fixture plans are never presented as Olist performance measurements.

## OpenAPI, schema export and actual HTTP

```bash
docker compose run --rm migrate spectacular --format openapi-json --validate --fail-on-warn
python3 scripts/database_schema.py verify --report .local/analysis-reports/schema-new.json
```

Strict schema validation checks structural consistency and warnings, not every semantic permission rule. The current exported [OpenAPI](../reports/recovery/local/openapi.json) includes report parameters/envelope, supported filters and JWT security. The schema tool compares [sql/schema.sql](../sql/schema.sql) with current migration-created DDL and restores both export/reference into new temporary databases. It preserves checks/casts/triggers and removes only databases created by that invocation. Current schema evidence confirms 28 tables and 22 migrations. The schema dump excludes rows, ownership and grants; a schema-only restore has no applied migration history. Use migrations for normal creation, and reapply grants separately. See [schema restoration details](stage-02/setup.md#schema-export-and-isolated-restore-verification).

The old `verify_database_roles.py` is an empty-history Stage 2 probe and deliberately refuses populated history; do not run it on imported environments. Populated-data authorization is exercised by application tests and retained HTTP/source evidence instead.

The [execution guide](getting-started.md) provides `scripts/verify_curl.py` for actual shell curl workflows on a confirmed fresh seeded demo. It appends simulated data, refuses used targets/output and never resets a database. Its output stores transport exit codes, HTTP statuses and selected assertions, omitting credentials/tokens/raw login responses. The current API 1.4.0 [closeout curl artifact](../reports/closeout/curl.json) (50 requests) comes from that actual transport, not an illustrative command transcript.

Full historical query outputs/measurements are separate from test fixtures. [Stage 5 SQL results](../reports/stage-05/sql-results.json) disclose bounded samples, full counts and ordered hashes. [The experiment](stage-05/index-experiment.md) retains 30 actual EXPLAIN plans, seven measured runs per phase, medians, buffers, index bytes and equivalence. Final documentation verification does not rerun or relabel that dated experiment.

API 1.2.0 passed **184 PostgreSQL tests locally and on GitHub Actions**, including 27 new expiry/verification tests. Dated execution evidence is in [reservation verification](reservations/verification.md). The focused command exercises `tests.test_reservation_expiry`, `tests.test_order_idempotency` and `tests.test_operational_services` against PostgreSQL. `scripts.verify_reservations` additionally exercises real HTTP/CLI with explicitly scoped fictional fixture time travel; its target guards have dedicated tests. That API 1.2.0 verification did not exercise a scheduler, a real elapsed 30-minute wait or a fresh historical benchmark; API 1.3.0 adds the separately verified optional worker.

API 1.3.0 passed **204 PostgreSQL tests locally and on GitHub Actions** and adds worker configuration/signal/target tests and PostgreSQL worker lifecycle/metrics tests. [Worker delivery verification](worker/verification.md) records actual counts/commands; the preceding API 1.2.0 evidence remains dated. Tests inject deterministic failure/wait coordination rather than sleeping through the interval. Actual Docker verification additionally observes completed JSON events before SIGTERM, ensuring a real process wakes from its configured wait. The worker changes no table/migration/API route; schema restoration still checks the exact current 28 tables/22 migrations.

Current recovery-tool tests additionally validate exported-snapshot isolation using a separate committed writer connection, all-table/password/migration hashing, read-only enforcement, unsupported-key and unsafe-sequence refusal, private/exclusive outputs, changed-checksum rejection, distinct-cluster guards and owned-helper cleanup after two frontend timeouts. [Recovery verification](recovery/verification.md) records executed counts and actual separate-cluster restores. CI uses fictional fixtures; actual full Olist recovery is separately retained local evidence, not a dataset download or workload executed on every push.

API 1.4.0 passed **221 PostgreSQL tests locally and on GitHub Actions**, including 17 new recovery tests. Earlier stage/feature counts remain dated. The actual historical restore faithfully used its 20-migration source; full-suite schema checks use the unchanged current 22-migration model.

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

The Stage 6 suite executed **130 tests** against PostgreSQL, not SQLite. The CI extension executed **137** tests; API 1.1.0 passed **157 tests** locally, including 20 creation-key tests. See the [current verification](idempotency/verification.md) and dated [CI evidence](ci/verification.md) for actual executed results. The `tests` service uses `olist_test`, creates/destroys `test_olist_case_study` and does not flush the application database. Run suites serially against a given target; concurrent suite invocations can collide on Django's test database name. Do not substitute application/owner credentials for the test service.

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
| Concurrency | 20 controlled operational scenarios with separate PostgreSQL connections/backend PIDs, coordination events and observed blocking; includes last-unit races, reversed multi-offer input, cancellation/payment, pricing and adjustments |
| Creation keys | Canonical equivalence, scoped ownership/current authorization, null-safe hash constraints, conflict/replay status and headers, unchanged legacy creation, rollback reuse, edited catalog/current lifecycle replay; five controlled advisory/order-lock races |
| Import | Locked identity/content, structural failures/duplicates, anomaly preservation, atomic failure, no-op/corruption, concurrent import lock, durable sanitized attempt metadata |
| SQL reports | Multiple item/payment facts without multiplication, repeat identity, canceled/empty intervals, HAVING/ranking ties, missing versus zero, calendar windows, delivery eligibility and seller association deduplication |
| Analysis/verification tools | Demo seed refusal/rollback, benchmark cleanup after injected failure, preexisting index preservation, wrong-target refusal and curl write-target/loopback guards |

Concurrency tests rely on controlled coordination and observed database locks rather than only arbitrary delays. Passing observed schedules does not prove every possible production schedule or deadlock absence. Miniature benchmark protocol tests use real PostgreSQL DDL/EXPLAIN with a test-only mocked isolated-target guard; their fixture plans are never presented as Olist performance measurements.

## OpenAPI, schema export and actual HTTP

```bash
docker compose run --rm migrate spectacular --format openapi-json --validate --fail-on-warn
python3 scripts/database_schema.py verify --report .local/analysis-reports/schema-new.json
```

Strict schema validation checks structural consistency and warnings, not every semantic permission rule. The current exported [OpenAPI](../reports/idempotency/local/openapi.json) includes report parameters/envelope, supported filters and JWT security. The schema tool compares [sql/schema.sql](../sql/schema.sql) with current migration-created DDL and restores both export/reference into new temporary databases. It preserves checks/casts/triggers and removes only databases created by that invocation. Current schema evidence confirms 28 tables and 21 migrations. The schema dump excludes rows, ownership and grants; a schema-only restore has no applied migration history. Use migrations for normal creation, and reapply grants separately. See [schema restoration details](stage-02/setup.md#schema-export-and-isolated-restore-verification).

The old `verify_database_roles.py` is an empty-history Stage 2 probe and deliberately refuses populated history; do not run it on imported environments. Populated-data authorization is exercised by application tests and retained HTTP/source evidence instead.

The [execution guide](getting-started.md) provides `scripts/verify_curl.py` for actual shell curl workflows on a confirmed fresh seeded demo. It appends simulated data, refuses used targets/output and never resets a database. Its output stores transport exit codes, HTTP statuses and selected assertions, omitting credentials/tokens/raw login responses. The final [curl artifact](../reports/idempotency/curl.json) comes from that actual transport, not an illustrative command transcript.

Full historical query outputs/measurements are separate from test fixtures. [Stage 5 SQL results](../reports/stage-05/sql-results.json) disclose bounded samples, full counts and ordered hashes. [The experiment](stage-05/index-experiment.md) retains 30 actual EXPLAIN plans, seven measured runs per phase, medians, buffers, index bytes and equivalence. Final documentation verification does not rerun or relabel that dated experiment.

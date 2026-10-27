# Stage 5 verification

Executed on 2026-10-26. This delivery adds historical SQL reports, an isolated full-snapshot index experiment and a separate fictional operational seed. [changes.md](changes.md) lists every created/changed file; [review.md](review.md) records independent review. Stage 6 remains subject to the user's technical review.

## Application and PostgreSQL checks

The final [checks.json](../../reports/stage-05/checks.json) retains exact command arrays, exit codes and output. All seven commands exited 0:

```bash
docker compose run --rm --entrypoint python app -m pip check
docker compose run --rm --entrypoint ruff app check --no-cache .
docker compose run --rm --entrypoint ruff app format --check --no-cache .
docker compose run --rm migrate check
docker compose run --rm migrate makemigrations --check --dry-run
docker compose run --rm migrate migrate --check
docker compose run --rm tests
```

Results: no broken dependencies, lint/format passed, Django checks reported no issues, no migration changes, and **125 PostgreSQL tests passed in 10.453 seconds**. Tests used a separate `test_olist_case_study` database created/destroyed by the test role; no SQLite fallback. The existing registration/JWT, access isolation, constraints, transactional rollback, price snapshots, cancellation and controlled separate-connection contention tests were rerun. The 15 operational concurrency scenarios coordinate locks and observe PostgreSQL blocking rather than depending on arbitrary sleeps.

New SQL tests cover multiple items plus multiple payments without multiplication, customer reference versus repeat identity, cancellation filters, HAVING thresholds, ranking ties, zero-filled months, missing facts versus observed zero, delivery exclusions and seller association deduplication. Reviewer feedback corrected a same-day estimated-date predicate in both delivery reports; an explicit regression test verifies a midnight estimate with a purchase later that same day. An earlier 124-test run passed before that additional regression; the retained final suite is the 125-test run after correction.

Demo tests check hashed accounts, ledger/status outcomes, populated-target refusal and atomic rollback. Benchmark protocol tests use real PostgreSQL DDL/EXPLAIN on a small fictional fixture, with the isolated-target guard explicitly mocked only in those unit tests. They check cleanup after an injected failure, preservation/refusal of a preexisting candidate and minimum repetitions/target guards. Their temporary fixture plans are **not** the real-data performance evidence.

## Schema, documentation and live HTTP

```bash
python3 scripts/database_schema.py verify --report reports/stage-05/schema-verification.json
docker compose run --rm migrate spectacular --format openapi-json --validate --fail-on-warn
```

The schema verifier confirmed the unchanged SQL export matches the migration-created database and an isolated PostgreSQL restoration: **28 tables, 20 migrations**. It also compares constraints, indexes, sequences, functions and triggers after PostgreSQL reparsing. No benchmark index remains in the export or application schema. [Schema verification](../../reports/stage-05/schema-verification.json) records hashes and restore scope; grants must still be reapplied separately as documented in Stage 2.

Strict OpenAPI validation exited 0 without warnings for **38 paths**: [command result](../../reports/stage-05/openapi-verification.json), [current OpenAPI](../../reports/stage-05/openapi.json). The current health endpoint returned HTTP 200 with `{"status":"ok","stage":5}`, and the running image matched the image used for tests/analysis. Actual runtime packages are Python 3.12.15, Django 5.2.18, DRF 3.18.3, SimpleJWT 5.5.1, psycopg 3.3.6, drf-spectacular 0.30.0, Ruff 0.17.2 and PostgreSQL 17.11 on aarch64. Docker Engine 29.9.2 and Compose 5.6.1 are recorded in [runtime.json](../../reports/stage-05/runtime.json).

The live service received **19 HTTP requests**: anonymous report access 401, customer access 403, all 12 admin reports 200, unknown report 404, invalid interval input 400, and second-page coverage 200 with 20 rows, plus two successful logins. Each admin report's count and first row matched independently executed SQL in the separate full-snapshot database. [http.json](../../reports/stage-05/http.json) records outcomes, not passwords or tokens. The curl examples illustrate the verified API; they are not presented as separately executed shell requests.

## Actual datasets, SQL and index measurements

Both isolated environment setup command sequences exited 0. The benchmark importer, running as restricted `olist_importer`, accepted **451,535 source rows / 451,537 entities**, rejected 0 and retained 3,739 warnings across 3,116 rows. It imported the complete locked archive distribution without generating extra historical sales. See [datasets.md](datasets.md), [import summary](../../reports/stage-05/benchmark-import.json) and [benchmark database verification](../../reports/stage-05/benchmark-database.json).

`run_olist_reports` exited 0 and executed **12 reports**. [sql-results.json](../../reports/stage-05/sql-results.json) preserves parameters, exact SQL hashes, full counts/ordered-result hashes and bounded samples. It is not a full export of large result sets. The [SQL portfolio](sql-portfolio.md) explains each business question, grain, SQL features, cancellation and empty/NULL handling. Delivered-order repeat buyers were **2,801 of 93,358 eligible identities (3.00%)** in the defined interval, based on executed SQL.

`benchmark_olist` exited 0 against `olist_benchmark`. It preserved **30 actual JSON plans**: 9 warm-ups and 21 measured runs. Median server execution was **5.356 ms baseline**, **0.080 ms indexed**, **5.135 ms control after index removal**, seven measured runs per phase. Index size was **8,282,112 bytes (7.90 MiB)**. Ordered results and complete historical field/relationship fingerprints remained equal. The temporary candidate was confirmed absent afterward. The [experiment report](index-experiment.md) gives individual measurements, plan/buffer changes, settings, storage and warm-cache limitations; [summary.json](../../reports/stage-05/index-experiment/summary.json) and all raw plans are retained. This is a measured result for one query, not an API-wide speedup or an adopted production migration.

The small seed command exited 0, creating 4 hashed users, 3 customers, 2 products, 2 sellers, 3 offers and 5 orders, one per lifecycle state. Balances **18/17/19** match the ledger. A repeat seed intentionally exited 1 with `DEMO_SEED_REFUSED` and preserved the populated target. A benchmark attempt against `olist_case_study` intentionally exited 1 before output/index creation. These are successful refusal checks, not unresolved failures. Exact command evidence is in [demo-commands.json](../../reports/stage-05/demo-commands.json) and [primary-target-refusal.json](../../reports/stage-05/primary-target-refusal.json).

## Preservation and remaining work

The existing service retained its 3 operational orders, 5 items, 12 stock movements, one simulated payment and one shipment; balances remain **0/8/4**, equal to the ledger. Its source content/relationship hashes still match the accepted manifest. The benchmark has no simulated rows; the small demo has no historical rows. [Primary database verification](../../reports/stage-05/primary-database.json), [demo verification](../../reports/stage-05/demo-database.json) and runtime volume inventory document separation. The original legacy checkout and its volume were preserved.

No unresolved application/test failures remain in this delivery. Source inconsistencies are deliberately retained and disclosed, not silently repaired. Current limits include one accepted snapshot, no historical review/geolocation model, bounded report parameters with offset pagination, no real inventory/payment integration, one fixed warm-cache benchmark query, and no production index adoption. Full final-guide consolidation and portfolio presentation belong to Stage 6 after technical review.

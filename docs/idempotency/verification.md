# API 1.1.0 creation-key verification

## Scope and isolation

This delivery continues from published revision `a761a9c` and the local paused checkpoint `17df774`, resumed on 2026-10-27. It adds optional creation idempotency to the simulated operational API. Historical Olist import, source facts, SQL reports and the dated index experiment are unchanged. Reservation expiry remains outside scope.

The preserved review project is `olist-idempotency-review`, database `olist_demo`, loopback API port 18026, with its own `olist-idempotency-review_olist_postgres_data` volume. Its ignored mode-0600 configuration is `.local/idempotency/review.env`. Baseline seeding used the previous Stage 6 image and 20 migrations before applying the new additive migration. No primary, benchmark, demo or legacy database was targeted. The disposable CI pipeline used a different randomly allocated project, database, image and volume.

## Migration and existing data

The [baseline setup](../../reports/idempotency/baseline-setup.json) and [focused checks](../../reports/idempotency/focused-checks.json) preserve actual commands/output. The migration adds nullable hashes, a null-safe pair/format CHECK and customer/key partial uniqueness. Existing rows retain both NULL fields.

Actual resume commands included:

```bash
docker compose -p olist-idempotency-review --env-file .local/idempotency/review.env up -d --wait db
python3 .local/idempotency/capture.py after-migration
```

The ignored local capture helper reads all `accounts_%`, `catalog_%`, `inventory_%`, `orders_%` and `olist_%` tables, ordered by table name and row ID. For each row it hashes PostgreSQL `(to_jsonb(t) - 'idempotency_key_hash' - 'request_fingerprint')::text`, joined with newlines as UTF-8. Only counts and SHA-256 digests are published; row contents/password hashes are not. [Before](../../reports/idempotency/before-migration.json) and [after](../../reports/idempotency/after-migration.json) match exactly for all **23 domain tables**. The latter records **21 migrations and five legacy orders with NULL pairs**. This demonstrates migration preservation on this fictional baseline; it is not a fresh verification of every existing environment.

The candidate export command was `python3 scripts/database_schema.py export --schema .local/idempotency/schema.sql`, with inherited `COMPOSE_*` stripped and explicit `COMPOSE_PROJECT_NAME=olist-idempotency-review`, absolute `COMPOSE_FILE`, absolute `COMPOSE_ENV_FILES` and `COMPOSE_PROFILES=tools`. Review found only two columns, their CHECK, the partial unique index and randomized dump safety tokens changed. The reviewed candidate became `sql/schema.sql`; it contains no data, owners or grants.

## PostgreSQL checks

The focused command executed before the pause was:

```bash
docker compose -p olist-idempotency-review --env-file .local/idempotency/review.env run --rm tests test tests.test_order_idempotency --noinput --verbosity2
```

**20 tests passed in 1.000 second**, including five controlled separate-connection races. Each race observes actual blocking using backend PIDs and PostgreSQL lock/activity evidence: same key before the first row exists; different content under the same key; first transaction rollback after writes; replay waiting for cancellation; and account revocation while waiting. These tests do not depend only on delays. Other assertions cover canonical content, key scope/case/grammar, current permissions, snapshots, full rollback, failed-key reuse, status/header contracts, internal-field privacy and database constraints.

On resume, the complete command was:

```bash
python3 -m scripts.run_ci --output .local/idempotency/ci-final
```

All **nine phases exited 0**, including all **seven verification commands**: dependency consistency, Ruff lint/format, Django checks, migration drift/applied checks and the complete suite. **157 PostgreSQL tests passed in 11.377 seconds**. The role probe passed **75 checks**; strict OpenAPI produced API **1.1.0 / 38 paths**; schema restoration confirmed **28 tables / 21 migrations** and matching exported DDL. Two fresh restore-check databases and the disposable CI resources were cleaned up by the guarded runner. [Independent host cleanup checks](../../reports/idempotency/local-cleanup.json) found no remaining CI containers, volume, network or image tag and confirmed the primary/benchmark/demo/review/legacy volumes and old Stage 6 image still exist. Evidence: [summary](../../reports/idempotency/local/summary.json), [checks](../../reports/idempotency/local/checks.json), [roles](../../reports/idempotency/local/roles.json), [OpenAPI](../../reports/idempotency/local/openapi.json), [schema](../../reports/idempotency/local/schema.json), [runtime](../../reports/idempotency/local/runtime.json).

Actual application runtime remains Python 3.12.15, Django 5.2.18, DRF 3.18.3, PostgreSQL 17.11, SimpleJWT 5.5.1, psycopg 3.3.6 and Ruff 0.17.2 on local aarch64. No dependency upgrade is claimed. The local source-input hash identifies the candidate before README's later evidence/feature-summary edits; [provenance reconstruction](../../reports/idempotency/local-provenance.json) reproduces it exactly using that README. Runtime code/SQL did not change after this successful run. Hosted evidence identifies its exact published revision separately.

## Real HTTP transport

```bash
docker compose -p olist-idempotency-review --env-file .local/idempotency/review.env up -d --wait app
python3 scripts/verify_curl.py --project olist-idempotency-review --env-file .local/idempotency/review.env --output reports/idempotency/curl.json --allow-demo-writes
```

The guarded runner confirmed source-free fresh fictional seed counts, API database role and loopback binding before any writes. **50 real curl requests passed**. The [artifact](../../reports/idempotency/curl.json) retains method/path, expected/actual HTTP status, transport exit code and observed replay header; passwords/tokens/raw login responses are omitted. Private curl configuration travels on stdin. This invocation used ordinary Python, not Python `-O`.

Observed behavior includes 201/false creation, 200/true same-order canonical replay, 409 content conflict, 400 malformed key, denied anonymous/admin replay, unchanged snapshots after repricing/renaming, cancelled-state replay without another reservation, unkeyed creation without a replay header, full insufficient-stock rollback and corrected reuse of the unconsumed key. Stock/ledger assertions cover the existing multi-seller processing workflow. The runner appends data and refuses a second run against a used target; it never resets the database.

## Review, release and limitations

Independent review and file inventory are recorded in [review](review.md) and [changes](changes.md). The actual hosted run is documented below; local and hosted results identify separate environments and revisions.

This release does not automatically migrate existing running primary/demo containers. Follow the [existing-environment update guide](../getting-started.md#updating-an-existing-operational-environment) deliberately using the correct project/env. Existing data volumes and old image tags are retained. Successful keys have no expiry, unkeyed calls remain unsafe for automatic ambiguous retries, replay returns current state rather than cached bytes, and the guarantee ends at the database transaction. Passing coordinated schedules does not prove every possible schedule or production throughput. No new Olist index measurements, real payment processing or production deployment occurred.


## Actual hosted execution

Publishing `f66c253ae6a47ec4a74cc84a0e71a6b4d735379f` triggered the successful push-to-main [GitHub Actions run 40554533387](https://github.com/joaoltrevisan/django-orders-inventory-portfolio/actions/runs/40554533387) on 2026-10-27. [Run metadata](../../reports/idempotency/github-run.json) records the exact head, event, successful job/steps and timestamps. [Artifact metadata](../../reports/idempotency/github-artifacts.json) identifies the uploaded archive and retention.

All nine phases and seven check commands exited 0. **157 PostgreSQL tests passed in 13.236 seconds**, including 20 actual observed operational contention records; **75 role checks passed**. Strict OpenAPI retained **API 1.1.0 / 38 paths**. Schema/export/restoration checks confirmed **28 tables / 21 migrations** and the exact current SQL file hash. Actual hosted runtime was Python 3.12.15 / PostgreSQL 17.11 on x86_64. Durations differ from local aarch64 and are not a performance comparison.

The six downloaded files are retained byte-for-byte: [summary](../../reports/idempotency/github/summary.json), [checks](../../reports/idempotency/github/checks.json), [roles](../../reports/idempotency/github/roles.json), [OpenAPI](../../reports/idempotency/github/openapi.json), [schema](../../reports/idempotency/github/schema.json), [runtime](../../reports/idempotency/github/runtime.json). The source-input fingerprint reconstructed from the exact tested Git revision matches the artifact. [Log/artifact inspection](../../reports/idempotency/github-log-review.json) found no configured local secret or JWT/GitHub-token/private-key pattern; raw logs remain ignored. Deleted ephemeral hosted passwords are unavailable for an exact-value rescan, so this is not a claim of exhaustive secret detection.

The independent reviewer checked the actual hosted evidence and source/schema hashes and found no material blocker. This final documentation/evidence commit may trigger another CI run; the immutable retained artifacts above refer specifically to `f66c253`, not an unexecuted later revision. There is no deployment or new benchmark claim.

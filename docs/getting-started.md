# Execution guide

Use Docker Engine with Compose v2+, Python 3.11+ on the host, and curl for HTTP examples. Python application dependencies run inside the pinned Python 3.12.15 container; a host virtual environment is optional. Run commands from the repository root. Current image: `olist-case-study-app:1.4.0`; health returns `{"status":"ok","stage":6}`. [Runtime evidence](../reports/recovery/local/runtime.json) records versions actually used.

There are two independent paths: a small operational demonstration that needs no source download, and historical analysis using the locked Olist archive. Existing service data is a third, preserved environment. Never substitute one project's env file for another's or remove populated volumes to repeat an example.

## Path A: operational demonstration

For a new demonstration environment:

```bash
python3 scripts/create_analysis_env.py demo
mkdir -p .local/analysis-reports .local/import-reports
docker compose -p olist-demo --env-file .local/analysis/demo.env build app
docker compose -p olist-demo --env-file .local/analysis/demo.env up -d --wait db
docker compose -p olist-demo --env-file .local/analysis/demo.env run --rm migrate
docker compose -p olist-demo --env-file .local/analysis/demo.env run --rm migrate configure_database_roles
docker compose -p olist-demo --env-file .local/analysis/demo.env \
  run --rm --user "$(id -u):$(id -g)" -e DEMO_SEED_ENABLED=1 migrate seed_demo \
  --expected-database olist_demo --report /reports/demo-seed-new.json
docker compose -p olist-demo --env-file .local/analysis/demo.env up -d --wait app
curl --fail-with-body -sS http://127.0.0.1:18022/health/
```

Skip the env generator if its file already exists. Skip seeding if the database is already populated: the command refuses to replace data. Use a new report filename for every invocation. The owner tool's report appears under `.local/analysis-reports`; host UID/GID permits writing that bind mount while the web application still runs as nonroot `app`.

The seed creates 4 fictional hashed accounts, 2 products, 2 sellers, 3 offers and 5 orders, covering the original five operational states, with balances 18/17/19. Administrator email is `admin@example.com`; customer emails are `customer1@example.com` through `customer3@example.com`. Their private generated password is `DEMO_PASSWORD` in the ignored mode-0600 demo env file. No historical customers, orders or prices are copied into this domain. No payment provider is called. See [dataset details](stage-05/datasets.md).

Execute the documented workflow with **real curl**, without exposing token/password arguments:

```bash
python3 scripts/verify_curl.py --project olist-demo \
  --env-file .local/analysis/demo.env --output .local/analysis-reports/curl-new.json \
  --allow-demo-writes
```

The runner verifies the connected database is `olist_demo`, the role is `olist_api`, historical orders are absent, the baseline seed counts match and the published port is loopback. It then appends fictional accounts/catalog/orders/movements and checks registration/login/refresh, keyed creation/replay/conflicts/recovery, multi-seller snapshots, cancellation once, simulated processing, rollback and access boundaries. Secrets travel in curl configuration on stdin, not argv or evidence. It uses returned IDs. This is a **single workflow on a freshly seeded target**, not an idempotent/reset command; a previously used target is refused. Do not rerun failed or completed writes blindly. The current API 1.4.0 closeout used an additional independent project/volume and passed 50 real curl requests; see [delivery verification](delivery.md#final-verification). The earlier [Stage 6 verification](stage-06/verification.md) remains dated evidence. Both deliveries preserved existing demo data.

Use [API examples](api.md) to explore individual requests. Historical reports return 409 in the source-free demo because no completed historical snapshot exists.

## Path B: historical import, SQL and index analysis

Obtain the archive from the [official Olist source](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), respecting [attribution and licensing](../THIRD_PARTY_DATA.md). Put the ZIP at ignored `.local/olist/brazilian-ecommerce.zip`. The locked archive SHA-256 is `967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784`; the accepted package manifest is [olist/source-manifest.json](../olist/source-manifest.json). A mismatched archive is refused. There is no automatic download bundled with service startup.

```bash
python3 scripts/create_analysis_env.py benchmark
mkdir -p .local/analysis-reports .local/import-reports
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env build app
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env up -d --wait db
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env run --rm migrate
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env run --rm migrate configure_database_roles
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env \
  run --rm --user "$(id -u):$(id -g)" importer import_olist \
  --archive /data/brazilian-ecommerce.zip --manifest /app/olist/source-manifest.json \
  --expected-database olist_benchmark --report /reports/import-new.json
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env \
  run --rm --user "$(id -u):$(id -g)" migrate run_olist_reports \
  --expected-database olist_benchmark --output /reports/sql-new.json
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env \
  run --rm --user "$(id -u):$(id -g)" -e OLIST_BENCHMARK_ENABLED=1 migrate benchmark_olist \
  --expected-database olist_benchmark --output /reports/index-new
```

Skip existing env generation; use fresh output filenames/directories. Importer output maps to `.local/import-reports`; owner analysis output maps to `.local/analysis-reports`. The importer uses `olist_importer`, validates before atomic publication and writes a full anomaly report. An identical verified rerun is `NOOP`; a different/corrupted snapshot is refused. Add `--dry-run` with a new report filename to validate without publishing domain/attempt rows. [Import contract](stage-03/import.md) describes rejection, duplicate prevention, timestamp handling and durable attempt reporting.

The benchmark contains **451,537 historical entities**, including 99,441 orders, with no operational simulation rows. It does not require a web container or administrator account. The benchmark command refreshes statistics and creates/removes only its own experimental index, preserving all 30 plans by default. It never resets the database or overwrites results. The [SQL portfolio](stage-05/sql-portfolio.md) and [dated experiment](stage-05/index-experiment.md) explain actual executed evidence and its limits; the Stage 6 presentation does not imply a new performance experiment.

## Existing application environment

For a fresh primary installation, generate `.env` once; if it already exists, preserve it. Main database and port are `olist_case_study` and `127.0.0.1:18020`:

```bash
python3 scripts/create_env.py
mkdir -p .local/analysis-reports .local/import-reports
docker compose build app
docker compose up -d --wait db
docker compose run --rm migrate
docker compose run --rm migrate configure_database_roles
docker compose up -d --wait app
curl --fail-with-body -sS http://127.0.0.1:18020/health/
```

Startup creates schema, not accounts or source data. If an administrator is needed in a fresh empty primary installation, use interactive `docker compose run --rm migrate createsuperuser`; provide fictional `example.com` identity and a private password. Public registration never grants staff access. Do not recreate existing administrators. Import into the primary database only deliberately through the restricted importer with its expected database name; the separate analysis path is preferable for experiments.

After every migration, reapply `configure_database_roles`. PostgreSQL initialization credentials apply only on first volume creation; editing an env file does not rotate existing roles. [Architecture](architecture.md) explains role privileges. [Testing](testing.md) explains schema-only export/restore checks and disposable PostgreSQL tests.

`docker compose down` with the correct project/env arguments stops that project's containers/network and retains its named volume; restarting uses `up -d --wait db app`. Do not use `down -v`, `flush`, truncation or shared project names to reproduce this project. Source ZIPs, env files, payloads, tokens and full local issue reports remain ignored. The image excludes those inputs and reports; it includes only the fixed SQL files required at runtime. This is local development execution, not a production deployment recipe.

## Updating an existing operational environment

API 1.2.0 adds `orders.0003_reservation_expiry` (and applies earlier missing migrations, including `0002_creation_idempotency`) without rewriting historical/order rows. Preserve the existing env file and volume; build the current image, apply migrations, reapply classified grants, then recreate the API container using the same Compose project/env selection. For the default primary project:

```bash
docker compose build app
docker compose run --rm migrate
docker compose run --rm migrate configure_database_roles
docker compose up -d --wait app
```

For named demo/analysis projects, consistently supply their existing `-p` and `--env-file` options instead. Do not regenerate credentials, reseed a populated target or remove volumes. Old orders keep NULL creation hashes; clients opt into safe retry for new purchases with the [documented header](api.md#creation-keys-and-safe-retry). Health's stage remains 6 because the six original stages are complete; the OpenAPI API version is 1.4.0. An existing running container does not upgrade merely by pulling repository changes. This delivery's migration/HTTP verification targets a separate review database, preserving existing primary/benchmark/demo environments.

## Verify reservation expiry in a separate review environment

Normal operation uses the [explicit administrative command](api.md#reservation-deadlines-and-explicit-expiry) after a real deadline. For a faster reproducible verification, create a **new** private env/project following Path A with `PGDATABASE=olist_demo`, a free loopback port and project name `olist-reservation-review` (or that prefix plus a lowercase suffix). Preserve existing env files/volumes. Build/migrate/grant/seed/start it using that same project and env selection.

```bash
python3 -m scripts.verify_reservations --project olist-reservation-review \
  --env-file .local/reservations/review.env --output .local/analysis-reports/expiry-new.json \
  --allow-new-fixture-time-travel
```

This verification tool requires an explicitly named review project, source-free `olist_demo`, API role and IPv4 loopback binding. It appends new fictional customer/catalog/order data, then uses the owner tool to shift **only its new, owned, unprocessed order/reservation** backward one hour, retaining a 30-minute deadline. This is disclosed test-fixture preparation, not an API capability or a claim to have waited 30 minutes. It verifies actual late-payment rejection, owner-role refusal, API-role expiry/repetition, restored stock and expired keyed replay using real curl/CLI. Existing rows are not reset. Credentials remain on curl stdin; output excludes tokens/passwords. New evidence filenames are required and appending another run creates another fixture. Never use this tool against primary/benchmark data.

## Optional periodic expiry

API/image 1.3.0 adds the opt-in [worker overlay and operating guide](worker/operations.md). It reuses the existing expiry service and needs no new migration beyond the current 22. Existing installations still need deliberate image rebuild/recreation, unchanged schema/grants checks and an explicitly selected active actor/database before enabling scheduling. Default Compose and CI do not start the worker. Preserve credentials/data and never automatically regenerate or reseed an existing environment. Existing env files will need the new nonsecret worker options set deliberately; the safe template uses placeholders.

## Logical recovery drill

Image/API 1.4.0 adds the [private recovery workflow](recovery/operations.md), using a read-only source and a different recovery-review PostgreSQL cluster. It creates only new generated destination databases and compares actual rows/migrations/schema; no new model migration is introduced. Backup bundles stay ignored and private. Existing environments are not upgraded or overwritten. A restored older schema needs deliberate migrations/grants before application access, and its exact-restore evidence remains separate from that later upgrade.

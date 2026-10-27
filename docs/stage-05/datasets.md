# Separate demonstration and historical analysis environments

Stage 5 adds two independent Compose projects, databases, credential files and volumes. Existing application and legacy data are preserved. The historical benchmark uses the actual accepted Olist archive, not inflated or fictional sales. The small operational demonstration uses fictional identities and simulated inventory, prices, payments and delivery actions.

| Environment | Compose project / database | Persistent volume | Contents |
| --- | --- | --- | --- |
| Existing service | `olist-case-study` / `olist_case_study` | `olist-case-study_olist_postgres_data` | Preserved existing imported source and operational demonstration |
| Historical analysis | `olist-benchmark` / `olist_benchmark` | `olist-benchmark_olist_postgres_data` | Accepted historical snapshot only; operational tables empty |
| Small demonstration | `olist-demo` / `olist_demo` | `olist-demo_olist_postgres_data` | Fictional operational seed only; historical tables empty |

All use the same pinned Stage 5 application image and PostgreSQL 17.11. Only the existing service's web container is currently running. Optional demo web startup binds loopback port 18022; the benchmark configuration reserves 18021, but no benchmark web container is needed. PostgreSQL ports are not published. [Runtime evidence](../../reports/stage-05/runtime.json) records separate volumes and actual versions.

## Create private configuration and schema

From the repository root, with Docker running:

```bash
python3 scripts/create_analysis_env.py benchmark
python3 scripts/create_analysis_env.py demo
mkdir -p .local/analysis-reports .local/import-reports
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env build app
```

Skip each generator if its destination already exists. They refuse overwrite, create ignored mode-0600 `.local/analysis/benchmark.env` and `.local/analysis/demo.env`, generate distinct credentials from the placeholder template, and preserve the application's `.env`. The demo file also contains a generated `DEMO_PASSWORD`. Do not commit these files or print them in evidence. PostgreSQL initialization reads the credentials on first volume creation; changing an env file does not rotate an existing database's roles.

Provision each isolated schema and its restricted roles:

```bash
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env up -d --wait db
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env run --rm migrate
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env run --rm migrate configure_database_roles

docker compose -p olist-demo --env-file .local/analysis/demo.env up -d --wait db
docker compose -p olist-demo --env-file .local/analysis/demo.env run --rm migrate
docker compose -p olist-demo --env-file .local/analysis/demo.env run --rm migrate configure_database_roles
```

These exact operations succeeded for both new environments: [benchmark setup](../../reports/stage-05/setup-benchmark.json), [demo setup](../../reports/stage-05/setup-demo.json). No database copy, flush or reset of the existing service is involved. Keep both the `-p` project and `--env-file` arguments together on every command.

## Import the historical analysis snapshot

Obtain the archive from the [official Olist source](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and retain the local source metadata as explained in the [import guide](../stage-03/import.md). The locked archive SHA-256 is `967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784`. Place it at ignored `.local/olist/brazilian-ecommerce.zip`; the importer mounts this directory read-only. Source attribution, version ambiguity and CC BY-NC-SA 4.0 obligations are in [THIRD_PARTY_DATA.md](../../THIRD_PARTY_DATA.md).

```bash
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env \
  run --rm --user "$(id -u):$(id -g)" importer import_olist \
  --archive /data/brazilian-ecommerce.zip \
  --manifest /app/olist/source-manifest.json \
  --expected-database olist_benchmark \
  --report /reports/benchmark-import-new.json
```

The importer uses `olist_importer`, not the application/owner role. It validates source identity, keys, relationships and content, publishes atomically, prevents duplicates, and preserves warning-level source anomalies. The full report appears at `.local/import-reports/benchmark-import-new.json`; use a fresh filename. An identical validated rerun is a verified `NOOP`, not an extra copy; different/corrupted content is refused. Reviews and geolocation are fingerprinted but deferred from the model.

The actual separate import accepted **451,535 source rows**, represented by **451,537 entities**: 99,441 customer references, 73 categories, 32,951 products, 3,095 sellers, 99,441 orders, 112,650 items and 103,886 payment records. It rejected **0** rows and retained **3,739 warnings across 3,116 rows**. [Import summary](../../reports/stage-05/benchmark-import.json) and [database fingerprints](../../reports/stage-05/benchmark-database.json) preserve actual results. Row-level issue details stay local. This dataset supplies historical prices and payment records, never current catalog prices, balances, logins or payment processing.

## Generate the small fictional demonstration

```bash
docker compose -p olist-demo --env-file .local/analysis/demo.env \
  run --rm --user "$(id -u):$(id -g)" -e DEMO_SEED_ENABLED=1 migrate seed_demo \
  --expected-database olist_demo --report /reports/demo-seed-new.json
```

The command requires the literal isolated database, owner role, explicit enablement, a strong private password and an empty historical/operational domain. It obtains a transaction-scoped advisory lock and creates the complete seed atomically through the existing transactional services. It refuses a populated database rather than replacing or silently merging data. A second invocation with a new report filename was deliberately tested: expected exit 1, `DEMO_SEED_REFUSED`, existing data preserved. See [command evidence](../../reports/stage-05/demo-commands.json).

The seed contains an administrator `admin@example.com` and customers `customer1@example.com` through `customer3@example.com`, all using Django password hashing. It creates **2 fictional products, 2 sellers, 3 offers, 5 orders with 6 items**, including a multi-seller order and one order in each allowed state. Opening supply is 20 units per offer; the resulting balances are **18, 17 and 19**, equal to the audit ledger. There are 10 stock movements, 3 simulated payments and 2 simulated shipments. No historical record is inserted. [Seed summary](../../reports/stage-05/demo-seed.json) and [database verification](../../reports/stage-05/demo-database.json) record actual outcomes and password-hash verification without credentials.

Business content is repeatable in a fresh isolated environment; password salts, UUID references and event times deliberately differ between fresh runs. The generator has no reset option. Do not delete existing volumes to rerun it. Optional web startup:

```bash
docker compose -p olist-demo --env-file .local/analysis/demo.env up -d --wait app
```

Use the private demo password with the [authentication and operational API guides](../stage-04/api.md). This source-free environment returns 409 for historical business reports until a completed historical snapshot exists; keep historical imports in the separate benchmark environment.

## Execute reports and the index experiment

```bash
docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env \
  run --rm --user "$(id -u):$(id -g)" migrate run_olist_reports \
  --expected-database olist_benchmark --output /reports/sql-results-new.json

docker compose -p olist-benchmark --env-file .local/analysis/benchmark.env \
  run --rm --user "$(id -u):$(id -g)" -e OLIST_BENCHMARK_ENABLED=1 migrate benchmark_olist \
  --expected-database olist_benchmark --output /reports/index-experiment-new
```

Owner tools mount `/reports` at `.local/analysis-reports`, whereas the restricted importer uses `.local/import-reports`. Create the directories first; passing the host user permits writing evidence without changing the application's runtime user. Use a new output filename/directory each time; neither command overwrites evidence. Benchmark defaults are three warm-ups and seven measured runs in each of baseline/index/control phases. It checks the completed locked source and empty simulation domain, refreshes statistics, creates/removes only its own candidate index, verifies result/data equivalence and preserves raw JSON plans. An existing candidate name is refused and preserved.

The benchmark was also explicitly refused against the existing service database before creating output or an index: [target refusal](../../reports/stage-05/primary-target-refusal.json). It has no automatic reset. The SQL collection is documented in [sql-portfolio.md](sql-portfolio.md); the actual before/after measurements, storage cost and limitations are in [index-experiment.md](index-experiment.md). Use the committed actual evidence for this delivery; a new run is a new experiment, not a replacement for earlier measurements.

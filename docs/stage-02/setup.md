# Stage 2: isolated Docker execution

This stage provides models, migrations, database constraints/roles, a health endpoint, and PostgreSQL tests. Registration/order/import/report endpoints are not implemented yet. The older API's source and containers remain separate and unchanged.

## Create this project's environment

From this repository root, with Python 3 and Docker Engine/Compose available:

```bash
python3 scripts/create_env.py
docker compose config --quiet
docker compose build app
docker compose up -d --wait db
docker compose run --rm migrate
docker compose run --rm migrate configure_database_roles
docker compose up -d --wait app
curl --fail --silent --show-error http://127.0.0.1:18020/health/
```

If `.env` already exists, preserve it and skip the generator. It creates a private mode-0600 file with six distinct generated secrets, prints no values, and refuses overwrite. `.env.example` contains placeholders only. Do not run with its placeholder values as actual credentials. Rebuild the image after source changes.

The Compose project is `olist-case-study`; its volume is `olist-case-study_olist_postgres_data`. Database `olist_case_study` is reachable only inside the Compose network. The app binds to `127.0.0.1:18020` by default; change `APP_PORT` in your own `.env` if needed. No raw Olist input, secret file, Git metadata, documentation report, or SQL dump is copied into the application image.

The only current HTTP endpoint is `GET /health/`; it executes a database probe with the restricted API login. Its successful response is `{"status":"ok","stage":2}`. No source dataset is imported by starting containers or applying migrations. No simulated customers, stock, orders, or payments are seeded.

This is a local development server, not public production hosting. `docker compose down` stops this project's containers while preserving its volume. Resume with `docker compose up -d --wait db app`. Do not remove volumes or reuse the old project's Compose name/database. Initialization SQL runs only for a **new** volume; changing password strings later does not rotate passwords in an existing PostgreSQL cluster.

## Role separation

| Compose service | PostgreSQL role | Privileges |
| --- | --- | --- |
| `migrate` | `olist_owner` | Owns database/schema and migration objects; no superuser, role creation, or database creation |
| `app` | `olist_api` | DML on simulation/auth tables, SELECT on historical and required Django metadata; no historical writes, DDL, role switching, or database creation |
| `importer` | `olist_importer` | SELECT/INSERT on historical tables; UPDATE only import-run state and snapshot publication status; no history correction/deletion, operational writes, or DDL |
| `tests` | `olist_test` | CREATEDB for disposable Django test databases only; cannot assume owner/API/importer privileges |
| Bootstrap inside `db` | `postgres` | Creates the isolated roles; never application/import/test credentials |

After **every migration**, run `configure_database_roles` with the owner service. It reclassifies existing objects and applies grants. Default privileges for objects created by `olist_owner` grant the API SELECT only; new tables fail closed for writes until explicitly classified. Newly added importer tables fail closed until grants are reapplied. Schema export intentionally excludes grants and cannot restore this boundary by itself.

The app/importer can read `django_migrations` for Django management checks; they cannot edit migration history. API connection uses a real password over container-network TCP. The additional permission-verification helper uses separate local psql sessions inside the isolated container to exercise each role's authorization; it does not claim to test password authentication for every role.

## Execute checks

```bash
python3 scripts/verify_stage2.py --output .local/stage-02/checks-new.json
```

The command runs pip checks, Ruff lint/format checks, Django checks, migration drift/applied-state checks, and the current PostgreSQL test suite, preserving actual stdout/stderr and exit codes. Choose a new output name; existing evidence is not overwritten. It assumes the image is built, database initialized, migrations applied, and grants configured. It stops on failure. The test role creates/destroys its own `test_olist_case_study` database; it does not reset the application's database.

The permissions probe is deliberately **Stage 2 only, before import**:

```bash
python3 scripts/verify_database_roles.py --report .local/stage-02/roles-new.json
```

It refuses any nonempty historical table with an explicit guard. Expected-denial operations execute inside transactions that roll back even if privileges unexpectedly allow them. A UUID-named future-table probe checks owner default privileges and is removed only if this invocation created it. It does not alter domain rows. Later stages need populated-data-safe authorization tests rather than running this empty-domain probe after import.

## Schema export and isolated restore verification

The committed `sql/schema.sql` is schema-only, generated from the migrated PostgreSQL 17.11 database. It includes tables, sequences, FKs, checks, unique/index definitions, and the immutable-offer trigger/function, but no rows, credentials, ownership, or grants.

```bash
python3 scripts/database_schema.py verify --report .local/stage-02/schema-new.json
```

Verification first compares the committed export with the live migration-created schema, excluding dump headers/random safety tokens only. It then restores the export and a separate current-reference dump into two fresh UUID-named databases and compares their complete re-dumped DDL. PostgreSQL can rewrite equivalent array casts during DDL reparsing; both sides receive identical database normalization without removing checks or casts. Only those new temporary databases are removed afterward.

To generate a new candidate after later migrations without overwriting the committed evidence:

```bash
python3 scripts/database_schema.py export --schema .local/stage-02/schema-candidate.sql
```

Review and update the committed schema deliberately, then rerun verification. A restored schema has an **empty** `django_migrations` table because this is a structural export, not an application backup. Use `manage.py migrate` for normal database creation; do not treat a schema-only restore as proof that migrations have been applied. Recreate roles/reapply grants separately when performing an actual structural restore.

Actual versions, commands/results, encountered failures, and remaining work are recorded in this stage's verification record. No historical import, operational order service, or benchmark is claimed here.

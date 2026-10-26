# Stage 2: actual verification evidence

Date: 2026-10-26. Implementation scope: isolated PostgreSQL/Docker setup, selectively adapted models, constraints, migrations, restricted roles, schema export/restore comparison, health probe, and model/verification tests. No source-data import or business API endpoints were implemented.

## Executed checks and retained results

| Actual command | Result |
| --- | --- |
| `python3 scripts/create_env.py` | Created private `.env`; no secret values printed; generation/no-overwrite/template tests passed |
| `docker compose config --quiet` | Exit 0 |
| `docker compose build app` | Successful after the download-timeout correction described below |
| `docker compose up -d --wait db` | New isolated PostgreSQL container healthy |
| `docker compose run --rm migrate` | All 20 migrations applied, including the offer identity trigger |
| `docker compose run --rm migrate configure_database_roles` | Scoped grants applied; later correction adds SELECT-only migration metadata access |
| `docker compose up -d --wait app` | Healthy after the metadata-grant correction |
| `python3 scripts/verify_stage2.py --output reports/stage-02/checks.json` | Exit 0; pip, Ruff lint/format, Django checks, migration drift/applied-state checks, and all **39 tests** passed |
| `python3 scripts/verify_database_roles.py --report reports/stage-02/database-roles.json` | All **75** real role-session authorization checks passed |
| `python3 scripts/database_schema.py export` | Schema-only export created without overwriting an existing file |
| `python3 scripts/database_schema.py verify --report reports/stage-02/schema-verification.json` | Export matches source schema; isolated full-DDL restoration comparison passed; 28 tables; no row data or grants included |
| `docker compose run --rm --entrypoint python app -m scripts.runtime_versions` | Actual container/runtime/database versions captured |
| Host HTTP request to `http://127.0.0.1:18020/health/` | HTTP 200; `{"status":"ok","stage":2}` using the restricted API database login |

The [checks artifact](../../reports/stage-02/checks.json) preserves every consolidated command, actual stdout/stderr, exit code, and completed test count. The first complete suite had 36 passing tests; three verification-safety regression tests were then added after review, and the final 39-test suite passed. Pure environment/verifier unit checks share the PostgreSQL-configured suite; do not interpret every test as a separate database integration test.

Coverage includes source/customer identity separation, source key/sequence uniqueness and FKs, repeated historical product lines/multiple payments, zero values/incomplete dates, singleton snapshots, nullable categories, finite source money, source-clock preservation and unsafe-transform refusal, multi-seller model representation, offer reassignment trigger, purchase snapshots, quantity/stock/movement/lifecycle constraints, password hashing/email equivalence, a JWT dependency round-trip smoke check, health errors, environment protection, and verifier safety regressions.

The [runtime artifact](../../reports/stage-02/runtime.json) records Python/package/server versions, architecture, Docker versions, actual image identities, database role/time zone, and health response. Core actual versions are Python 3.12.15, Django 5.2.18, DRF 3.18.3, SimpleJWT 5.5.1, PyJWT 2.15.1, psycopg 3.3.6, PostgreSQL 17.11, and Ruff 0.17.2. A successful JWT encode/decode smoke check is not a complete API authentication test or proof of upstream support for every version combination; Stage 3 retains that integration gate.

## Failures encountered and corrections

1. Initial Docker build exited 2 after a `files.pythonhosted.org` read timeout. Retried with pip timeout 120/retries 3; removed the unused Swagger sidecar package. The next build succeeded with the pinned versions. No certificate verification was disabled.
2. Host-side initial migration generation could not inspect PostgreSQL history at localhost because that was not the isolated container endpoint. It emitted a warning while generating files; subsequent migration generation/drift checks ran inside Docker against the actual database and found no changes. No host/legacy database was changed.
3. Initial lint checks found import ordering and long lines in new/generated files. Formatting/import fixes were applied; final container Ruff lint/format checks passed.
4. First app startup exited because Django's development server checks `django_migrations`, which had no API grant. Granted SELECT only to API/importer, retained no UPDATE/INSERT/DELETE privileges on that table, rebuilt/reapplied grants, and confirmed app health over TCP/HTTP.
5. Initial schema restoration comparison falsely differed because PostgreSQL rewrites equivalent varchar-array coercions during DDL reparsing. Kept a strict export-versus-current comparison and added identical PostgreSQL reparse normalization on both full DDL sides. No constraints or casts are removed by normalization. Final comparison passed; regression test ensures SQL checks/casts remain intact.
6. Independent review found that role-denial probes could autocommit if permissions unexpectedly allowed them. Wrapped probes in BEGIN/ROLLBACK, replaced the nonempty-history assertion with an explicit refusal, and limited cleanup to objects this invocation created. Added regression tests and reran the final suite/authorization checks.
7. The first runtime-version collector invocation used a direct script path, which omitted the project root from Python's import path. Invoke it as `python -m scripts.runtime_versions`; this module command resolves Django settings from the application root.
8. A later rebuild initially failed because Docker Desktop was stopped. Started the existing Docker Desktop installation, rebuilt successfully, and restarted only this project's app against its preserved database volume.
9. Final review found an outdated expected JWT audience after the service identity changed. Updated the smoke test to assert both the configured audience and issuer, rebuilt the image, and reran all seven consolidated checks with 39 tests passing. Earlier successful check/runtime artifacts remain private under `.local/stage-02/`; committed evidence describes the final image.
10. The staged diff check reported a generated blank line at the end of the PostgreSQL schema dump. Removed only that trailing empty line, then reran export/live and isolated restoration comparison and refreshed the schema file fingerprint. SQL statements and the normalized schema fingerprints remain unchanged.

No unresolved test/build/startup/schema failure is being presented as a pass. Initial failures remain documented; retained successful artifacts describe the corrected implementation.

## Data preservation and current limits

The old repository remains clean at `21b5b17`; its existing app/database containers and volume were not recreated or removed. After Docker Desktop resumed, those legacy containers remained exited; both the legacy `loja-stage3-20261023223148_postgres_data` volume and new volume were confirmed present. Only the new app/database were started and verified healthy. New roles, database, network, and volume belong only to `olist-case-study`. Raw source ZIP/metadata remain ignored under `.local/olist/`. The application database contains no imported historical rows or seeded simulation rows; framework permission/content-type/migration metadata is expected after migrations. Test fixture rows existed only in the disposable Django test database.

No registration/login/order/import/report endpoints, operational transaction services, controlled purchase concurrency, SQL business results, index experiment, or public deployment are claimed in this stage. Source import, raw/parsed validation, completed-snapshot publication, HTTP object permissions, and full JWT behavior remain Stage 3 or later work. Mermaid source is updated; visual rendering is not claimed.

The schema-only export is not a data backup or a migration-history restore. Roles/grants need their own setup. The permission probe is Stage 2-only and refuses populated historical data. API/importer roles do not replace application authorization, and schema owners can still change source facts deliberately.

Stop for the user's technical review after the independent final review and publication. Stage 3 does not start automatically.

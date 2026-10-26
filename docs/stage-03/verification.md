# Stage 3: executed verification

Date: 2026-10-26. Scope: validated historical import, read-only historical APIs, registration/JWT/profile/customer administration, seller/product/offer APIs, and current OpenAPI. This is the third of six development stages. Source import and HTTP execution used the isolated `olist-case-study` Compose project; the old repository/database were not reused.

## Commands and actual outcomes

| Command or executed check | Actual result |
| --- | --- |
| `docker compose build app` | Final Stage 3 image built successfully |
| `python3 scripts/verify_stage2.py --output reports/stage-03/checks.json` | Seven commands exit 0; **67 tests passed** against PostgreSQL; dependency/lint/format/Django checks passed; no migration drift/unapplied migrations |
| `docker compose run --rm --user "$(id -u):$(id -g)" importer import_olist ... --dry-run --report /reports/dry-run.json` | `DRY_RUN`; 0 writes/imports/rejections/duplicates; 3,116 inconsistent rows; 9.297 seconds |
| Same importer without `--dry-run`, report `full-import.json` | `SUCCEEDED`; 451,535 source rows represented by 451,537 entities; 0 rejections/duplicates/parent failures; 38.773 seconds |
| Same importer, report `verified-noop.json` | `NOOP`; 451,537 verified entities skipped; 0 imported; 13.491 seconds |
| Same importer with final image, report `final-noop.json` | `NOOP`; complete content and metadata verification passed after the final URL validation correction |
| `docker compose run --rm migrate spectacular --format openapi-json --validate --fail-on-warn` | Exit 0; **27 paths**, no schema warnings/errors after corrections |
| `docker compose up -d --wait app` and real HTTP client | Healthy; **18 HTTP requests** matched expected statuses, including 401/403/405 access restrictions |
| `python3 scripts/database_schema.py verify --report reports/stage-03/schema-verification.json` | Existing schema export still matches migrations/live DB and isolated restoration; 28 tables, 20 migrations, no schema change required |
| `docker compose run --rm --entrypoint python app -m scripts.runtime_versions` plus read-only DB/HTTP probes | Actual versions, image/user, HTTP 200, imported counts and API history permissions recorded |

The consolidated verifier's filename reflects its Stage 2 origin; the same seven checks execute the **current** complete test suite, not an old image/test subset. Exact commands, outputs and exit codes are preserved in [checks.json](../../reports/stage-03/checks.json). The earlier 58/65/66-test successful iterations remain local; the committed artifact contains the final 67-test run. Tests use a disposable PostgreSQL test database; source fixture archives are small, explicitly fictional records.

To repeat the complete current checks without overwriting committed evidence:

```bash
python3 scripts/verify_stage2.py --output .local/stage-03/checks-new.json
```

The existing application database and imported history remain intact; the test role creates and destroys only its disposable test database. Choose another output filename on subsequent runs.

The controlled import concurrency test pauses a real first importer at validation after it holds the advisory lock, observes its granted lock and different backend PID, invokes a second real importer, asserts `IMPORT_ALREADY_RUNNING` with no partial publication, then releases the first and verifies success followed by a no-op. Events and bounded waits provide coordination; no arbitrary sleep is used. Operational last-unit purchase races remain Stage 4 work.

Coverage includes atomic publication/rollback, durable failures, dry-run nonmutation, canonical duplicates, invalid keys/decimals/source times/parents, corrupted target/provenance refusal, signed reconciliation, NUL-safe diagnostics, metadata failure both before and after publication, and malformed manifest CLI reporting. Account/API tests cover hashing/password validation, registration/protected input, case-insensitive login, self-only name/phone updates, customer administration, deactivated/deleted/password-revoked/malformed/expired tokens, current staff privileges, direct-service authorization, catalog immutability/validation/zero-stock initialization, historical completion/admin/read-only boundaries, and source-clock serialization.

## Imported counts and observed quality

| Database entity | Executed count |
| --- | ---: |
| Historical customers | 99,441 |
| Distinct `customer_unique_id` values | 96,096 |
| Category union | 73 |
| Historical products | 32,951 |
| Historical sellers | 3,095 |
| Historical orders | 99,441 |
| Historical item rows | 112,650 |
| Historical payment records | 103,886 |

These counts were actually queried through the restricted API login and agree with the validated input. There are **3,739 warning issues across 3,116 distinct source rows**, not 3,739 rejected rows. Examples include 1,382 unexpected chronology sequences, 775 orders without items, 610 missing product categories, and zero-payment/missing-date facts. None was repaired.

Separately aggregated source item-plus-freight and payment totals yielded 98,665 comparable orders, 98,089 exact matches, and 303 differences above BRL 0.01, with maximum absolute difference BRL 182.81. Signed differences across all comparable orders sum to BRL 2,870.39. This reconciliation is not a sales ranking, profit statement, current price, or evidence of payment processing. Full SQL business reports and query optimization remain Stage 5 work.

The initial import and final no-op ran as `olist_importer`, not owner/test credentials. The API login was confirmed to lack any INSERT/UPDATE/DELETE/TRUNCATE privilege on tested historical fact tables. The historical import created no users, catalog offers, or inventory. Subsequent explicit HTTP demonstration created two fictional accounts (one administrator, one customer), one simulated product/seller/offer and a zero stock balance; no simulated order or stock movement was created. Private random passwords and JWTs are excluded from published artifacts.

## Evidence and reproducibility limits

Published artifacts are [dry-run](../../reports/stage-03/dry-run.json), [import](../../reports/stage-03/full-import.json), [first no-op](../../reports/stage-03/verified-noop.json), [final no-op](../../reports/stage-03/final-noop.json), [actual import commands](../../reports/stage-03/import-commands.json), [final command](../../reports/stage-03/final-noop-command.json), [database counts/permissions](../../reports/stage-03/database.json), [HTTP outcomes](../../reports/stage-03/http.json), [runtime](../../reports/stage-03/runtime.json), [schema verification](../../reports/stage-03/schema-verification.json), and [strict OpenAPI verification](../../reports/stage-03/openapi-verification.json). Complete issue/source-key and individual-delta JSON stays in ignored `.local/import-reports/`; each published summary records the full local report hash. Re-execution generates new reports; durations/attempt IDs/hashes are not promised to be identical across runs.

Import timings describe those individual executions, not controlled performance benchmarks or optimization gains. Input distribution was not inflated. No index experiment or query-plan evidence is claimed. Final runtime retains Python 3.12.15, Django 5.2.18, DRF 3.18.3, SimpleJWT 5.5.1, psycopg 3.3.6, and PostgreSQL 17.11. The tested authentication behavior is recorded without claiming broader upstream version-matrix certification.

The original repository remains clean at `21b5b17`. Its existing containers/volume remain separate; this delivery did not flush, migrate, remove or repurpose them. The schema helper creates/drops only its own temporary structural-verification databases; it exports no source rows.

## Corrections and limitations

Independent review identified metadata-finalization reporting, complete snapshot identity checks, canonical sequence collisions, stale/direct-service authorization, signed reconciliation details, malformed manifest CLI handling, and source URL type validation. All were corrected with targeted regression tests; review details are recorded separately. Strict OpenAPI generation initially failed on a missing custom JWT extension and colliding historical/operational serializer names; explicit scheme registration and historical component names fixed the warnings, then strict generation passed. Initial lint formatting issues were corrected before the successful consolidated runs.

A host-only account bootstrap helper initially attempted unsupported `Path.open(opener=...)` and failed before creating a secret file or account. It was corrected to built-in `open` with a mode-0600 creator; the standard Django `createsuperuser --noinput` command then succeeded using an environment-provided random password, never printed or committed.

Remaining work: operational order/stock/payment/lifecycle services and their races; repeatable simulated demonstration generator; historical SQL portfolio and measured index experiment; final end-to-end presentation. This local server has no public production deployment, distributed throttle store, real payments, or real Olist inventory/authentication integration. No unresolved executed check failure is being presented as a pass. Stop for user technical review before Stage 4.

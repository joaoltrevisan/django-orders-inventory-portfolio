# Completed service delivery

The **Order and Inventory Management Service for Olist**, by João Trevisan, has completed its six planned stages and the subsequently authorized CI, creation-key, reservation-expiry, optional-worker and private-recovery extensions. Current API/image version: **1.4.0**. This closeout consolidates acceptance evidence; it introduces no application behavior, migration, dependency or performance claim.

The service addresses Olist's marketplace context through a transactional demonstration API and separate historical analysis. It is independently developed using the attributed public dataset; it makes no claim of employment, a commissioned contract, partnership, endorsement or internal-system access. Operational accounts, offers, inventory, payment processing and fulfillment remain explicitly simulated.

## Completed requirements

| Requirement | Delivered implementation and evidence |
| --- | --- |
| Requirements before implementation | [Original rules/lifecycle](stage-01/requirements.md), [Olist adaptation and conflicts](olist/adaptation-plan.md), [current architecture](architecture.md), [operational contract](stage-04/rules.md) and later versioned designs |
| Supported stack and actual versions | Python 3.12.15, Django 5.2.18 LTS, DRF 3.18.3, PostgreSQL 17.11, SimpleJWT 5.5.1, psycopg 3.3.6; [pinned dependencies](../requirements.lock), [actual runtime](../reports/recovery/local/runtime.json), [Docker execution](getting-started.md) |
| Authentication, profiles and permissions | Django-hashed registration, JWT login/refresh, current-account checks, customer isolation, administrative customer/catalog/inventory/processing access and pagination; [API contract](api.md), [accounts](../accounts/services.py), [API tests](../tests/test_operational_api.py) |
| Relational integrity and SQL schema | [Mermaid ER diagrams](olist/data-model.md), [dictionary](olist/data-dictionary.md), PK/FK/unique/check/index explanations, migration-created [SQL export](../sql/schema.sql), [actual isolated restoration](../reports/recovery/local/schema.json) |
| Orders, multiple sellers and historical snapshots | Per-seller offers, server-side Decimal totals, immutable purchase prices/names, protected references and permitted transitions; [models](../orders/models.py), [services](../orders/services.py), [tests](../tests/test_operational_services.py) |
| Stock safety and audit | Atomic deduct-on-create, complete rollback, nonnegative stock, cancellation/release once, actor-attributed movements and consistently ordered locks; [inventory services](../inventory/services.py), [controlled PostgreSQL races](../tests/test_operational_concurrency.py), [current lock hierarchy](architecture.md) |
| Olist source semantics | Customer/order-reference versus repeat-customer identity, products/categories, sellers, multi-seller items, recorded payments, statuses and delivery clocks; [inspection](olist/inspection.md), [dictionary](olist/data-dictionary.md), [source manifest](../olist/source-manifest.json) |
| Repeatable import and preservation | Validated archive/member identity, duplicate prevention, verified no-op, atomic publication, rejected/inconsistent-record reporting; [import instructions](stage-03/import.md), [import tests](../tests/test_importer.py), [actual data/import evidence](stage-05/datasets.md) |
| Separate demonstration and benchmark data | Small fictional example.com seed with hashed passwords and a separate full historical snapshot/database; [guarded seed](../orders/management/commands/seed_demo.py), [reproducible paths](getting-started.md), [dataset sizes](stage-05/datasets.md) |
| SQL portfolio and executed results | Twelve reports with INNER/LEFT JOIN, aggregates/GROUP BY/HAVING, CTEs and windows, including repeat customers, sellers/categories, sales and delivery; [query explanations](stage-05/sql-portfolio.md), [SQL files](../sql/olist), [executed results](../reports/stage-05/sql-results.json), [correctness tests](../tests/test_sql_reports.py) |
| Evidence-based index experiment | Identical SQL/data, refreshed statistics, three warm-ups and seven measurements per phase, 30 actual JSON plans, buffers/index bytes, matching result hashes and removal control; [report](stage-05/index-experiment.md), [raw evidence](../reports/stage-05/index-experiment/summary.json) |
| Security and maintainability | Environment secrets, placeholders, least-privilege database roles, validated ORM/parameterized SQL, services, object access controls and sanitized English errors; [architecture](architecture.md), [safe template](../.env.example), [limitations](limitations.md) |
| Tests, API documentation and presentation | Real PostgreSQL suites, coordinated separate connections, strict OpenAPI, curl workflows, independent review; [test guide](testing.md), [current OpenAPI](../reports/recovery/local/openapi.json), [API examples](api.md), [technical presentation](portfolio.md) |
| Attribution and license | Public source/version ambiguity anchored by hashes; preserved historical facts, documented transformations and CC BY-NC-SA 4.0 obligations; [third-party data notice](../THIRD_PARTY_DATA.md) |

All six stage records remain under `docs/stage-01` through `docs/stage-06`. Earlier proposed contracts and test counts are dated records, not descriptions of the current feature set. [Release evidence](testing.md#release-evidence) separates those results.

## Final verification

The closeout began from clean published revision `8bec2938dec4b80e561d649aee8c214bfb1bcb76`. Its exact-head [GitHub Actions run 40635890141](https://github.com/joaoltrevisan/django-orders-inventory-portfolio/actions/runs/40635890141) succeeded; [retained metadata](../reports/closeout/baseline-ci.json) records the revision and successful steps. The final documentation commit receives a separate normal push-triggered CI run, checked before handoff. No later run is inferred from the baseline result.

A concurrent remote README edit (`d917a8d`) arrived before publication. The first push was rejected; the closeout commit was rebased onto that remote change, preserving it without force-pushing or changing application code.

The existing functional evidence was independently checked rather than rerun or relabeled:

| Executed verification | Actual result | Evidence |
| --- | --- | --- |
| Complete local PostgreSQL suite | 221 tests passed in 13.646 seconds | [Checks](../reports/recovery/local/checks.json) |
| Complete hosted functional suite, revision `882d36a` | 221 tests passed in 20.950 seconds | [Checks](../reports/recovery/github/checks.json), [exact run/revision](recovery/verification.md#actual-hosted-execution) |
| Database roles / strict OpenAPI / schema restoration | 75 checks passed; API 1.4.0 / 38 paths; 28 tables / 22 migrations | [Roles](../reports/recovery/local/roles.json), [OpenAPI](../reports/recovery/local/openapi.json), [schema](../reports/recovery/local/schema.json) |
| Fresh current-image operational HTTP closeout | 50 real curl requests passed, all transport exits 0 and expected statuses matched | [Curl requests and assertions](../reports/closeout/curl.json) |
| Historical SQL/index evidence | Preserved dated executed results; no new experiment claimed | [SQL results](../reports/stage-05/sql-results.json), [experiment](stage-05/index-experiment.md) |
| Independent closeout review | No mandatory blocker; two documentation inaccuracies corrected | [Review](closeout-review.md) |

For the fresh HTTP check, newly generated mode-0600 credentials under ignored `.local/closeout` selected project `olist-closeout-review`, database `olist_demo`, a new named volume and loopback port 18031. No existing data/configuration was reused or reset. [Setup commands, stdout/stderr and exit codes](../reports/closeout/setup.json) record successful image build, database startup, all migrations, role grants, guarded fictional seed and API startup. The seed contained four hashed accounts, five orders and three offers. Then this exact command exited 0:

```bash
python3 scripts/verify_curl.py --project olist-closeout-review \
  --env-file .local/closeout/review.env --output reports/closeout/curl.json \
  --allow-demo-writes
```

The runner also checked authenticated OpenAPI version 1.4.0. It confirmed registration/JWT, ownership/admin boundaries, a 91.80 multi-seller purchase, preserved snapshots after repricing, a 100.00 new-price purchase, keyed replay/conflicts, cancellation once, simulated processing and full insufficient-stock rollback. This writes only fictional data on that new target. Credentials/tokens travel on stdin and are omitted from evidence. Only this closeout project's app/database containers were stopped afterward; its data volume was retained. [Static/evidence checks](../reports/closeout/audit.json) record final local links/fences, evidence consistency, SQL hash and bounded secret scanning. These checks do not substitute for application tests.

The inline Python/stdlib static audit checked 67 Markdown files and their local link targets, with no missing target or unbalanced code fence in the final pass; it did not validate remote URLs or anchors. Its first pass exited 1 because it linked its own not-yet-created output. That [initial result](../reports/closeout/audit-first.json) is preserved, and the subsequent pass verified the created file and exited 0. `git diff --check` also exited 0. No application-test failure occurred in this closeout.

## Files changed in this closeout

- `README.md`, `docs/getting-started.md`, `docs/testing.md`, `docs/portfolio.md` and `docs/limitations.md`: lead with current results, retain dated evidence, correct concurrency wording and mark future work optional.
- `docs/delivery.md` and `docs/closeout-review.md`: acceptance mapping, actual final verification and independent-review outcome.
- `reports/closeout/setup.json`, `curl.json`, `baseline-ci.json`, `audit-first.json` and `audit.json`: actual setup/HTTP, immutable baseline CI and both static/evidence inspection passes.

Application code, dependencies, migrations, historical source rows and the prior SQL/index measurements are unchanged. The closing Git commit is the authoritative file inventory.

## Remaining boundaries and handoff

There is no unresolved mandatory implementation failure. Final user technical acceptance is the remaining review checkpoint; no further development stage is required by the agreed scope.

The delivered Compose service is local development execution. Public production deployment, real payment/warehouse/carrier integrations, distributed throttling, operational alerts, encrypted/offsite retention and PITR require separately scoped work. Logical recovery does not establish RPO/RTO, and controlled concurrency tests do not cover every possible schedule. The temporary index was removed; the measured warm-cache improvement applies only to its fixed historical query. Full [limitations](limitations.md) remain part of the delivery. Optional future work is outside this completed scope.

# API 1.3.0 worker delivery verification

## Scope and environments

This extends `0b6729c` with the opt-in worker defined in the [preimplementation contract](design.md). It reuses existing expiry transactions, adds optional between-order stopping, structured cycle outcomes and observational backlog. It introduces no dependency/table/migration/HTTP route or historical Olist change. Current image/API label is 1.3.0; package versions remain pinned.

Verification used a new `olist-worker-review` Compose project, database `olist_demo`, private mode-0600 `.local/worker/review.env` and its own named volume. Only fictional data was seeded. Existing primary, benchmark, demo, prior review and legacy environments were not upgraded or scheduled. The review worker was stopped at the end; no periodic task remains active from verification.

## Focused checks and review correction

The initial isolated command sequence started PostgreSQL, applied migrations/grants and executed:

```bash
docker compose -p olist-worker-review --env-file .local/worker/review.env run --rm tests test tests.test_expiry_worker tests.test_reservation_expiry --noinput --verbosity 2
```

[First result](../../reports/worker/focused-first.json): four commands exited 0 and **40 PostgreSQL tests passed in 1.814 seconds**. Independent review then identified a telemetry mismatch: an unexpected programming exception could retain the default `database_error` label. The worker now records `unexpected_error`, sanitizes details and exits without retrying it. A corresponding injected-failure test and three verification-target guard tests were added.

The [final focused sequence](../../reports/worker/focused-final.json) added `tests.test_worker_verification_safety`; all four commands exited 0 and **44 tests passed in 2.364 seconds**. No focused/full failure is relabeled as a pass; both successful focused runs identify their actual candidate scope.

## Complete PostgreSQL and schema verification

```bash
python3 -m scripts.run_ci --output .local/worker/ci-final
```

All nine phases and seven verification commands exited 0. **204 PostgreSQL tests passed in 13.256 seconds**, including 20 new worker/target-safety tests. The existing 28 operational contention schedules remain verified (25 observed waits, three SKIP LOCKED); new worker tests additionally observe a locked row from another PostgreSQL connection and deliver real SIGTERM at a controlled point inside an atomic release, proving its commit and the untouched next order. Wait/recovery/authority tests use deterministic coordination rather than waiting 60 seconds.

The role probe passed **75 checks**. Strict OpenAPI validates **API 1.3.0 / 38 paths**. SQL/live/isolated restoration confirms the unchanged **28 tables / 22 migrations**, including exact committed schema-file hash. No new schema export or index was needed. Normal disposable test-database destruction and guarded resource cleanup are retained in [summary](../../reports/worker/local/summary.json), [checks](../../reports/worker/local/checks.json), [roles](../../reports/worker/local/roles.json), [OpenAPI](../../reports/worker/local/openapi.json), [schema](../../reports/worker/local/schema.json) and [runtime](../../reports/worker/local/runtime.json).

Actual local application runtime: Python 3.12.15, Django 5.2.18, DRF 3.18.3, PostgreSQL 17.11, SimpleJWT 5.5.1, psycopg 3.3.6, Ruff 0.17.2 on aarch64. [Source reconstruction](../../reports/worker/local-provenance.json) reproduces the candidate fingerprint exactly before later README evidence edits; runtime/SQL inputs did not change after the successful run. Docs/reports are excluded by the driver.

## Actual container execution

After build/migrate/grants, the isolated owner tool seeded the standard five-order fictional dataset:

```bash
docker compose -p olist-worker-review --env-file .local/worker/review.env run --rm --user 501:20 -e DEMO_SEED_ENABLED=1 migrate seed_demo --expected-database olist_demo --report /reports/worker-seed.json
python3 -m scripts.verify_expiry_worker --project olist-worker-review --env-file .local/worker/review.env --output reports/worker/container.json --allow-new-fixture-time-travel
```

The [actual artifact](../../reports/worker/container.json) records 21 successful command checks, the initially confirmed source-free/API-role/seed identity and one newly appended fictional purchase. Only that new purchase/reservation's timestamps were shifted one hour to create an overdue fixture while retaining the 30-minute policy; no actual 30-minute waiting or API clock override is claimed. The helper refused an existing worker container before writes, stripped inherited Compose overrides and used explicit files/project/env.

Observed results:

- One finite process completed two cycles at the requested one-second interval: expired counts **[1, 0]**, with zero observed backlog after each, then normal limit shutdown.
- The optional service was started twice against that same database. After actual JSON cycle-completion events, Docker stop delivered SIGTERM during its 60-second interval; both sessions emitted signal shutdown and exited **0**. No guessed startup delay coordinates the stop.
- Final queried state was EXPIRED with **exactly one RELEASE** and **zero observed due backlog**. Later cycles/restart did not restore stock again. Both signal sessions and all finite JSON events are preserved.

This delivery verifies periodic CLI/process behavior; existing HTTP/API tests run in the full suite and earlier real-curl workflows remain dated evidence. It does not relabel those older HTTP executions as new ones.

## Isolation and limitations

[Actual resolved/inspected Compose facts](../../reports/worker/compose-isolation.json) confirm five default services/six only with the optional overlay, API database role, no worker published port/host mount, nonroot/read-only/init settings, restart policy `no`, 30-second stop grace and final stopped/exit-0 state. Secret-bearing resolved configuration is not published. [Cleanup/preservation inspection](../../reports/worker/local-cleanup.json) found no remaining disposable CI resources and confirmed seven old/new review data volumes and prior image tags remain; these are presence checks, not a fresh row audit of all earlier databases.

Backlog is an MVCC observation that can include locked rows and immediately change. Failed/unavailable observations are NULL, not invented zero. The attempt limit does not bound scan/wait/cycle duration. Per-statement timeouts and graceful stop do not guarantee completion before Docker's force-kill grace. Persistent corrupt oldest rows can starve later work until intervention; no quarantine/fairness or production-throughput claim is included. Default startup leaves the worker disabled. Production supervision, retained log monitoring/alerts and recovery drills remain explicit future work. Historical source/import/report/index artifacts were not changed or rerun.

See [independent review](review.md), [file inventory](changes.md) and [operations](operations.md). Hosted results are recorded separately only after actual execution, with exact revision/artifact provenance.


## Actual hosted execution

Successful push-to-main [GitHub Actions run 40630141048](https://github.com/joaoltrevisan/django-orders-inventory-portfolio/actions/runs/40630141048) tested exact revision `e3b30157d18121430cbe512a9dcb2b1bbe2f7ee1`. [Run metadata](../../reports/worker/github-run.json) records successful job/steps, event, revision and UTC timestamps (created 2026-10-28T04:03:28Z). [Artifact metadata](../../reports/worker/github-artifacts.json) identifies the uploaded archive/digest/retention.

All nine phases/seven check commands exited 0. **204 PostgreSQL tests passed in 18.228 seconds**, including the existing contention schedules and new worker stop/backlog facts, with normal test-database destruction. **75 role checks passed**. Strict OpenAPI retained **API 1.3.0 / 38 paths**. Schema/live/isolated restoration remained **28 tables / 22 migrations** and the SQL byte hash matches the committed file. Actual hosted runtime was Python 3.12.15 / PostgreSQL 17.11 on x86_64. Different local/hosted durations are not a performance comparison.

The six actual downloaded artifacts are retained byte-for-byte: [summary](../../reports/worker/github/summary.json), [checks](../../reports/worker/github/checks.json), [roles](../../reports/worker/github/roles.json), [OpenAPI](../../reports/worker/github/openapi.json), [schema](../../reports/worker/github/schema.json), [runtime](../../reports/worker/github/runtime.json). The source-input fingerprint reconstructed from the exact Git revision matches the summary. [Log/artifact inspection](../../reports/worker/github-log-review.json) found no inspected configured local secret or JWT/GitHub-token/private-key pattern. Raw logs stay ignored; deleted ephemeral hosted secrets are unavailable for an exact-value rescan, so this is not an exhaustive secret-detection claim.

The independent reviewer separately validated the actual hosted artifacts, exact source/schema hashes, downloaded-file identity and bounded log inspection and found no material blocker. These immutable artifacts refer to `e3b3015`. A later documentation/evidence commit triggers its own CI, checked separately. Hosted CI tests the code in an isolated database and leaves the optional recurring container disabled; actual Docker lifecycle evidence above came from the dedicated local review project. No production scheduler, deployment, historical download or new index measurement is claimed.

# API 1.2.0 reservation expiry verification

## Scope and preserved environments

This delivery starts at `d4d8ee1` and implements the [contract defined before code](design.md). It adds a fixed new-order payment deadline, explicit audited EXPIRED transition and bounded administrator command. Historical Olist source/import/query/index evidence is unchanged. No scheduler, real payment or public deployment is included.

Migration/HTTP verification uses only `olist-reservation-review`, database `olist_demo`, loopback port 18027 and its own named volume. Private configuration is `.local/reservations/review.env`, ignored and mode 0600. The preceding API 1.1.0 image seeded five fictional orders with 21 migrations before applying the new migration. Existing primary, benchmark, demo, idempotency-review and legacy environments were not migrated or reset.

## Actual migration preservation

[Baseline setup](../../reports/reservations/baseline-setup.json) records all four successful commands: start the new database, apply old migrations, configure grants and seed fictional data. The owner generated `orders.0003_reservation_expiry` using Django 5.2.18 and a bind mount of the current orders source, then the generated file was Ruff-formatted. [Focused checks](../../reports/reservations/focused-second.json) record actual new migration/grant/test invocations.

Ignored local capture commands were:

```bash
python3 .local/reservations/capture.py before-migration
python3 .local/reservations/capture.py after-migration
```

The helper hashes ID-ordered PostgreSQL `(to_jsonb(t) - 'reservation_expires_at' - 'expired_at')::text` rows joined with newlines, publishing only counts/digests. It includes all original fields, including creation-key hashes. [Before](../../reports/reservations/before-migration.json) and [after](../../reports/reservations/after-migration.json) match across **all 23 domain tables**. The after capture records **22 applied migrations and five legacy NULL deadline/expiry pairs**. The helper inherited the metadata label `hash_columns` from the earlier delivery: here it lists the two new timestamp columns, not hash columns. The actual captured values are preserved without relabeling them after execution.

`python3 scripts/database_schema.py export --schema .local/reservations/schema.sql` ran with inherited `COMPOSE_*` removed and explicit review project, absolute compose/env files and tools profile. The reviewed SQL export adds two columns, a temporal CHECK and updated status CHECK, plus randomized pg_dump safety tokens. No historical table, speculative index, row data, owner or grant was added to the export.

## Test corrections retained honestly

The first focused invocation stopped before executing tests because `--verbosity2` is not a valid option. [Initial record](../../reports/reservations/focused-first.json) retains exit 2. Correcting it to `--verbosity 2` yielded **61 PostgreSQL tests in 2.876 seconds**, covering the 24 new functional/concurrent expiry tests plus existing creation-key and order-service tests.

The first complete suite executed **184 tests in 13.148 seconds** and had one failure: a previous seed test assumed its five orders represent every possible status. EXPIRED now has a separate controlled verification fixture; the stable seed intentionally retains the original five states. The expectation was updated explicitly rather than changing populated seed data. [Initial full results](../../reports/reservations/preflight-checks.json) preserve the failure. A following preflight stopped at Ruff because that test edit had not yet been formatted; [format preflight](../../reports/reservations/format-preflight-checks.json) preserves that outcome and does not claim tests ran.

After correcting formatting, the final complete command was:

```bash
python3 -m scripts.run_ci --output .local/reservations/ci-verified
```

All **nine phases and seven verification commands exited 0**. **184 PostgreSQL tests passed in 12.607 seconds**. This includes **27 new tests**: 16 functional expiry tests, eight separately coordinated PostgreSQL races and three verification-target guard tests. In total, 28 operational concurrency scenarios emitted actual evidence: **25 observed blocking schedules and three SKIP LOCKED schedules**. Boundary-clock injection is deterministic test coordination, not a claim to wait a real 30 minutes. Normal disposable test-database destruction is recorded.

The role probe passed **75 checks**. Strict OpenAPI validates **API 1.2.0 / 38 paths**, read-only nullable deadline/expiry fields and late-payment/replay semantics. Export/live/isolated-restoration schema checks confirm **28 tables / 22 migrations**, including CHECKs, keys, triggers and exact SQL file hash. [Summary](../../reports/reservations/local/summary.json), [checks](../../reports/reservations/local/checks.json), [roles](../../reports/reservations/local/roles.json), [OpenAPI](../../reports/reservations/local/openapi.json), [schema](../../reports/reservations/local/schema.json) and [runtime](../../reports/reservations/local/runtime.json) are actual results.

Application versions remain Python 3.12.15, Django 5.2.18, DRF 3.18.3, PostgreSQL 17.11, SimpleJWT 5.5.1, psycopg 3.3.6 and Ruff 0.17.2 on local aarch64. [Cleanup inspection](../../reports/reservations/local-cleanup.json) confirms no remaining final CI resources and retained existing data volumes/old images; those presence checks are not a fresh row audit of the other databases. [Source reconstruction](../../reports/reservations/local-provenance.json) exactly identifies the candidate before later README evidence edits; runtime/SQL inputs did not change afterward.

## Actual HTTP and management command

The isolated API was built/started and the general workflow executed:

```bash
docker compose -p olist-reservation-review --env-file .local/reservations/review.env build app
docker compose -p olist-reservation-review --env-file .local/reservations/review.env up -d --wait app
python3 scripts/verify_curl.py --project olist-reservation-review --env-file .local/reservations/review.env --output reports/reservations/curl.json --allow-demo-writes
```

**50 real curl requests passed**: [general artifact](../../reports/reservations/curl.json). The additional expiry workflow was:

```bash
python3 -m scripts.verify_reservations --project olist-reservation-review --env-file .local/reservations/review.env --output reports/reservations/expiry-http-verified.json --allow-new-fixture-time-travel
```

It passed **16 real curl requests and three CLI checks**: [verified artifact](../../reports/reservations/expiry-http-verified.json). This fixture appends its own fictional customer/catalog/purchase and explicitly shifts only that new, owned, unprocessed order/reservation back one hour, retaining the 30-minute duration. It does not wait 30 minutes or provide a time-travel API. Existing rows are not reset. The script requires a dedicated review project, source-free `olist_demo`, API role, loopback binding and explicit fixture opt-in. Target guard tests reject other roles/databases/history/bindings.

Observed outcomes: overdue remains pending, late payment returns 409 without release, owner-role command returns 1 with the exact expected guard message, API-role command expires/restores once, repeated command does not re-expire the fixture, keyed replay returns the same EXPIRED order/deadline/snapshots, terminal cancellation/payment reject, final stock is five and the reservation/release ledger nets to zero. The initial [expiry artifact](../../reports/reservations/expiry-http.json) also passed 16 requests/three commands; the repeat strengthened owner-refusal evidence by asserting the specific message, following independent review. It created a second separate fictional fixture. General 50-request workflow was not unnecessarily repeated.

Credentials travel on curl stdin and are excluded from response evidence; raw login responses, env files and source data remain ignored. Role guard rejection is expected success of the verification, not an unresolved command failure.

## Review, release and limitations

See [independent review](review.md) and [file inventory](changes.md). Hosted CI is recorded separately after actual execution and must identify its exact revision. Existing running environments need deliberate additive migration/image update through the [execution guide](../getting-started.md); repository publication does not migrate them.

Successful keys remain retained and replay never renews deadlines. Thirty minutes is a demonstration policy. Explicit expiry needs external operational scheduling to run periodically; absent execution keeps units deducted. The command may skip locked rows and commits per order; it does not promise a complete sweep, global atomicity, fixed scan/wait duration or automatic handling of ambiguous commits. No new performance gain, source experiment, real provider or production-readiness claim follows.


## Actual hosted execution

Push-to-main [GitHub Actions run 40623871962](https://github.com/joaoltrevisan/django-orders-inventory-portfolio/actions/runs/40623871962) successfully tested exact revision `b57265dc72136ffba04ca3680a47e53a7d549500`. [Run metadata](../../reports/reservations/github-run.json) records the event, revision, job/steps and UTC timestamps (started 2026-10-28T02:56:55Z). [Artifact metadata](../../reports/reservations/github-artifacts.json) identifies the uploaded archive and retention.

All nine driver phases and seven verification commands exited 0. **184 PostgreSQL tests passed in 25.764 seconds**, with 25 actual blocking records/three SKIP LOCKED records and normal test-database destruction. **75 role checks passed**. Strict schema generation retained **API 1.2.0 / 38 paths**; SQL live/export/isolated restore checks confirmed **28 tables / 22 migrations** and the exact current SQL file hash. Actual hosted runtime was Python 3.12.15 / PostgreSQL 17.11 on x86_64. Local/hosted runtimes are from different environments, not a performance comparison.

Downloaded artifacts are retained byte-for-byte: [summary](../../reports/reservations/github/summary.json), [checks](../../reports/reservations/github/checks.json), [roles](../../reports/reservations/github/roles.json), [OpenAPI](../../reports/reservations/github/openapi.json), [schema](../../reports/reservations/github/schema.json), [runtime](../../reports/reservations/github/runtime.json). Reconstructing the source-input fingerprint from the exact tested revision matches the artifact. [Log/artifact inspection](../../reports/reservations/github-log-review.json) found no inspected configured local secret or JWT/GitHub-token/private-key pattern. Raw logs stay ignored; deleted ephemeral hosted passwords are unavailable for a later exact-value scan, so this is not an exhaustive secret-detection claim.

The independent reviewer separately checked the actual hosted evidence, downloaded-file identity, source/SQL hashes and bounded secret scan and found no material blocker. The final documentation/evidence commit may trigger another automatic run. These immutable retained artifacts refer specifically to `b57265d`; its later documentation revision is checked separately. No source download, historical benchmark, automatic expiry schedule or deployment was run by CI.

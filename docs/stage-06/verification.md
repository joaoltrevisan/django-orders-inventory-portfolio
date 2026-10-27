# Stage 6 final verification

Executed 2026-10-26 in America/Sao_Paulo (UTC-03); machine timestamps use UTC and may show 2026-10-27. This delivery consolidates the English execution/API/architecture/testing/portfolio guides, completes OpenAPI discovery and verifies the principal workflows with actual curl. It retains earlier stage evidence and source facts. [changes.md](changes.md) inventories files; [review.md](review.md) records independent review and corrections.

## Initial assessment and changes

The repository was clean at Stage 5 commit `a5ee261`; the legacy repository was clean at `21b5b17`. Existing Django services, constraints, migrations, datasets, SQL and measured plans were reused. Inspection found current README links into older feature snapshots and omitted OpenAPI report/filter details. No new domain model, migration, operational business rule or index was needed.

Canonical current guides now replace stage-specific entry points. Older execution/API guides carry a forward link and retain their original evidence. The data notice now describes the **implemented** import/transformations rather than claiming no import has run. Current API label is 1.0.0 and health stage 6; image tag is `olist-case-study-app:stage6`.

OpenAPI now documents the 12 report names; source-clock start/end/defaults/bounds, thresholds and page; the paginated report envelope/origin/date metadata; report error outcomes; operational status/customer filters; movement offer/order filters; and source order filters on item/payment lists. Dynamic row columns remain explicitly report-specific rather than inventing a universal result schema.

## Final checks actually executed

The [seven-command report](../../reports/stage-06/checks.json) records exact arrays, output, exit codes and test completion:

```bash
python3 scripts/verify_stage2.py --output reports/stage-06/checks.json
```

It executed pip check, Ruff lint/format, Django check, migration drift/applied-state checks and `docker compose run --rm tests`. All seven exited 0. **130 PostgreSQL tests passed in 10.323 seconds**, including five new curl-target/optimized-verification safety tests and the existing 15 controlled operational concurrency scenarios. The test database was created/destroyed separately. Earlier 129-test runs passed before the extra optimized-mode regression; the retained report corresponds to the final code/image.

```bash
docker compose run --rm migrate spectacular --format openapi-json --validate --fail-on-warn
python3 scripts/database_schema.py verify --report reports/stage-06/schema-verification.json
```

Strict OpenAPI validation exited 0 without warnings for **38 paths**: [command result](../../reports/stage-06/openapi-verification.json), [document](../../reports/stage-06/openapi.json). Parameter/envelope fields were inspected in the generated output. Schema verification confirmed the unchanged export matches migrations and isolated restoration, including constraints/indexes/functions/triggers: **28 tables / 20 migrations**. [Schema evidence](../../reports/stage-06/schema-verification.json) retains actual hashes and restore limitations.

## Actual operational curl workflow

A new Compose project `olist-release-review` / database `olist_demo` / volume `olist-release-review_olist_postgres_data`, port 18023, was provisioned with new private credentials. Schema/roles/fictional seed/startup all succeeded. The first real-curl attempt reached product creation but generated a lowercase hex SKU, correctly rejected by the existing uppercase SKU rule (400 versus expected 201). [Initial failed evidence](../../reports/stage-06/curl-initial-failed.json) is retained. The generator now uppercases the SKU suffix. Its first attempt's data and volume were preserved, not reset.

A second independent project/volume `olist-release-review-2`, port 18024, completed 39 curl requests in ordinary Python; [that evidence](../../reports/stage-06/curl-before-review.json) is retained. Review then identified that bare verifier assertions could be removed under optimized Python. They were replaced by explicit checks, requests were extracted from checks, and an optimized-mode mismatch regression was added. Host prerequisites were corrected to Python 3.11+.

A final fresh project/volume `olist-release-review-final`, port 18025, received independent credentials and seed, preserving both previous attempts. [Setup](../../reports/stage-06/setup-final.json) and [seed](../../reports/stage-06/demo-seed-final.json) record success. Actual final command:

```bash
python3 -O scripts/verify_curl.py --project olist-release-review-final \
  --env-file .local/stage-06/review-final.env \
  --output reports/stage-06/curl.json --allow-demo-writes
```

It exited 0 and **39 actual curl requests passed with Python optimization enabled**, retaining every explicit check and request. [curl.json](../../reports/stage-06/curl.json) records each method/path/status/transport exit plus selected assertions, not login bodies or credentials. Verified behavior includes registration/login/refresh/self profile, admin catalog/supply, customer role denial and foreign-order 404, a two-seller **91.80** purchase, unchanged name/price snapshots after edits, cancellation/restoration exactly once, a new-price **100.00** purchase, repeated simulated payment reference, paid-cancellation 409, shipping/delivery, full insufficient-stock rollback, balanced movement history, source-free report 409 and authenticated OpenAPI.

The runner uses returned IDs, private curl config on stdin and a new report filename. It checks the actual API-connected database/role, no source orders, baseline seed counts and loopback binding before writes. A used target and primary configuration were deliberately refused with nonzero exits before output/HTTP writes: [target-refusals.json](../../reports/stage-06/target-refusals.json). These expected refusals are not unresolved failures. Five automated safety tests cover those guards, config-as-data handling and optimized-mode mismatch failure. The standalone manual curl snippets are explanatory forms of these workflows, not additional claimed executions.

## Current historical curl and source preservation

The primary service was updated to the final image without data migrations or domain writes. A separate private harness used actual curl with private stdin configuration to run **24 historical requests**: authentication/role failures, all 12 reports, pagination, unknown report, invalid timestamp, source orders/items/payment records and current administrator-only schema. All statuses passed; each report's count and first row matched the executed Stage 5 SQL evidence. Recorded payment kind remained `HISTORICAL_RECORD`. [historical-curl.json](../../reports/stage-06/historical-curl.json) retains selected assertions and outcomes without credentials.

The source archive was also revalidated using the restricted importer with `--dry-run`, the locked manifest and expected `olist_benchmark` target. [Invocation](../../reports/stage-06/import-validation-command.json) and [sanitized summary](../../reports/stage-06/import-validation.json) record actual output. Dry-run publishes no historical or attempt rows; full row-level issues remain local. The original actual full import and 12-query results remain dated Stage 5 evidence. No performance experiment was rerun or relabeled.

Read-only database verification compared primary, benchmark and existing demo counts/balances with Stage 5 evidence and verified all mapped source facts/relationships. Historical fingerprints remain unchanged. Primary balances are still **0/8/4**; the existing small demo remains **18/17/19**. All available quantities equal movement sums and operational totals equal item totals. The final curl environment has its own appended fictional operations. No experimental index remains. [databases.json](../../reports/stage-06/databases.json) records actual comparisons.

## Runtime, corrections and remaining limits

[Runtime evidence](../../reports/stage-06/runtime.json) records matching final application image IDs in primary and successful curl environments, nonroot `app`, healthy stage 6 responses, Docker/Compose/curl and package versions. Actual application versions remain Python 3.12.15, Django 5.2.18, DRF 3.18.3, PostgreSQL 17.11, SimpleJWT 5.5.1, psycopg 3.3.6, drf-spectacular 0.30.0 and Ruff 0.17.2. Source clocks remain timezone-free; runtime database timezone is UTC for operational events.

During local evidence collection, invoking the runtime helper as a file omitted the repository import path; the collector was corrected to `python -m scripts.runtime_versions` and completed. This was a verification-harness invocation correction, not a service failure. An initial line-length lint finding in the new curl runner was corrected before successful final checks. No unresolved application/test failures remain.

After verification, only the three temporary review Compose projects were stopped with `down` **without volume removal**. Their data/evidence remain recoverable, and the primary, benchmark and existing demo environments were not stopped/reset. [Cleanup commands](../../reports/stage-06/cleanup.json) record actual outcomes. Runtime health/image evidence describes the verification moment before this cleanup; the primary service remains on the final image.

This delivery does not establish public deployment, real stock/payment/carrier integrations, production hardening, cold-cache performance or a production index adoption. Mermaid source is supplied/reviewed without a rendered-diagram export check. [Limitations and follow-ups](../limitations.md) explicitly describe these boundaries. All six planned stages are implemented; final user technical review remains the completion checkpoint for the delivery.

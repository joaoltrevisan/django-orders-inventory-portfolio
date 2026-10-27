# Creation-key delivery file inventory

This inventory includes the paused local implementation and the completion delivery relative to `a761a9c`.

| Files | Purpose |
| --- | --- |
| `orders/idempotency.py` | Key grammar/hashing, versioned canonical fingerprint and bound transaction advisory lock |
| `orders/models.py`, `orders/migrations/0002_creation_idempotency.py`, `sql/schema.sql` | Nullable identity/content hashes, null-safe pair CHECK and partial customer/key uniqueness; additive migration/export |
| `orders/services.py`, `orders/views.py` | Atomic scoped creation/replay, current authorization, conflict handling, coherent snapshots, HTTP headers/status and OpenAPI |
| `tests/test_order_idempotency.py`, `tests/controlled_concurrency.py` | Twenty focused tests, including five separate-connection contention scenarios with observed query/lock evidence |
| `compose.yaml`, `config/settings/base.py` | Current application image/API label 1.1.0; existing image tags retained |
| `scripts/verify_curl.py` | Real keyed/unkeyed HTTP workflows, response-header assertions and API version check |
| `README.md`, `docs/api.md`, `docs/architecture.md`, `docs/getting-started.md` | Current capability, API contract/example, lock design and additive update instructions |
| `docs/limitations.md`, `docs/testing.md`, `docs/portfolio.md`, `docs/olist/data-model.md` | Honest remaining limits, executed coverage, technical presentation and updated operational ER model |
| `docs/idempotency/design.md`, `checkpoint.md`, `verification.md`, `review.md`, `changes.md` | Rules defined before code, archived pause, actual commands/results, independent review and this inventory |
| `reports/idempotency/baseline-setup.json`, `before-migration.json`, `after-migration.json`, `focused-checks.json`, `curl.json` | Actual isolated migration preservation, focused tests and real HTTP evidence |
| `reports/idempotency/local-provenance.json` | Exact reconstruction of the local source-input fingerprint with its README version |
| `reports/idempotency/local-cleanup.json` | Host verification of exclusive CI cleanup and retained existing volumes/image |
| `reports/idempotency/local/*.json` | Six retained disposable CI outputs: summary, checks, roles, OpenAPI, schema and runtime |

`reports/idempotency/github/*.json` preserves six hosted artifacts; `github-run.json`, `github-artifacts.json` and `github-log-review.json` retain exact-revision run/artifact identity and bounded log/source-hash inspection. Private configurations, local helpers, credentials, raw logs and database volumes remain ignored and unpublished. Historical source files, importer/report logic and dated index-experiment artifacts are unchanged.

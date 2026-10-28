# Periodic worker delivery file inventory

Relative to `0b6729c`:

| Files | Purpose |
| --- | --- |
| `orders/worker.py`, `orders/management/commands/run_reservation_expiry.py` | Signals, observational backlog, sanitized cycle summaries and fixed-delay/reconnection/retry loop |
| `orders/reservations.py` | Optional between-order stop predicate and explicit stopped report; existing expiry rules retained |
| `compose.worker.yaml`, `.env.example` | Separate opt-in profile, least-privilege worker service and deliberately configured nonsecret placeholders |
| `compose.yaml`, `config/settings/base.py`, `scripts/verify_curl.py` | Current image/API version 1.3.0; default service set unchanged |
| `tests/test_expiry_worker.py` | Configuration, real signals, PostgreSQL stop/locked backlog, fresh connections/timeouts, failures/recovery/authority and fixed-delay tests |
| `scripts/verify_expiry_worker.py`, `tests/test_worker_verification_safety.py` | Actual isolated container cycles/restart/SIGTERM fixture and three refusal/acceptance safety tests |
| `README.md`, `docs/api.md`, `docs/architecture.md`, `docs/getting-started.md` | Current capability, explicit enable/stop/configuration and unchanged HTTP/schema scope |
| `docs/limitations.md`, `docs/testing.md`, `docs/portfolio.md` | Operational limits, executed evidence and technical presentation |
| `docs/worker/design.md`, `operations.md`, `verification.md`, `review.md`, `changes.md` | Rules before code, operating/retry/shutdown guide, actual results, independent review and this inventory |
| `reports/worker/focused-first.json`, `focused-final.json`, `container.json` | Actual focused commands and container events/queried final state |
| `reports/worker/compose-isolation.json`, `local-cleanup.json`, `local-provenance.json` | Real configuration/process facts, preserved resources and exact candidate reconstruction |
| `reports/worker/local/*.json` | Six actual disposable-CI summary/check/role/OpenAPI/schema/runtime artifacts |

Hosted artifacts/metadata are retained only after execution and documented in verification. No model, migration, SQL schema, historical importer/report or dated index measurement changed. Private configuration, raw logs, helpers and data volumes stay ignored.

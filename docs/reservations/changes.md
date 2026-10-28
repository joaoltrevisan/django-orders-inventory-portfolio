# Reservation expiry delivery file inventory

Relative to `d4d8ee1`, the delivery changes these groups:

| Files | Purpose |
| --- | --- |
| `orders/reservations.py`, `orders/management/commands/expire_reservations.py` | Authoritative wall clock, shared audited release, bounded per-order expiry and operational role/target/actor guards |
| `orders/models.py`, `orders/migrations/0003_reservation_expiry.py`, `sql/schema.sql` | Nullable legacy-compatible deadline/expiry fields, EXPIRED state and local temporal/status CHECKs |
| `orders/services.py`, `orders/lifecycle.py`, `orders/integrity.py` | New fixed deadlines, payment cutoff, shared cancellation restoration, terminal/replay history consistency |
| `orders/serializers.py`, `orders/views.py` | Read-only timestamp fields, lifecycle filter/state schema and late-payment documentation |
| `tests/test_reservation_expiry.py` | 16 functional tests and eight controlled separate-connection concurrency schedules |
| `tests/test_reservation_verification_safety.py`, `scripts/verify_reservations.py` | Three target safety tests and guarded real HTTP/CLI expiry fixture workflow |
| `tests/test_analysis_tools.py` | Explicit original-five-state seed expectation, preserving its existing dataset shape |
| `compose.yaml`, `config/settings/base.py`, `scripts/verify_curl.py` | Current image/API label 1.2.0 and matching general HTTP schema check |
| `README.md`, `docs/api.md`, `docs/architecture.md`, `docs/getting-started.md` | Current capability, deadline rules, command examples, locks and existing-environment update instructions |
| `docs/limitations.md`, `docs/testing.md`, `docs/portfolio.md`, `docs/olist/data-model.md` | Scheduling/partiality limits, test evidence, technical presentation and operational ER fields/constraints |
| `docs/reservations/design.md`, `verification.md`, `review.md`, `changes.md` | Rules before code, actual commands/results/corrections, independent review and this inventory |
| `reports/reservations/baseline-setup.json`, `before-migration.json`, `after-migration.json` | Actual isolated old-version seed and old-row preservation evidence |
| `reports/reservations/focused-first.json`, `focused-second.json`, `preflight-checks.json`, `format-preflight-checks.json` | Initial command/seed-expectation/format failures preserved alongside successful focused tests |
| `reports/reservations/curl.json`, `expiry-http.json`, `expiry-http-verified.json` | Actual general/initial/strengthened HTTP/CLI evidence |
| `reports/reservations/local/*.json`, `local-cleanup.json`, `local-provenance.json` | Six final CI artifacts, exclusive cleanup/preservation checks and exact candidate source reconstruction |

`reports/reservations/github/*.json` preserves the six actual hosted artifacts. `github-run.json`, `github-artifacts.json` and `github-log-review.json` identify the tested revision/run/archive and bounded log/source-hash inspection. Private env files, helpers, raw logs and database/source data are not published. No Olist historical importer/report/benchmark implementation or dated measurement is changed.

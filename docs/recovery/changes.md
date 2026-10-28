# Logical recovery delivery file inventory

Relative to `6e6a29f`:

| Files | Purpose |
| --- | --- |
| `scripts/recovery_state.py` | Read-only exported snapshot, fixed-format streamed row fingerprints, scope/key validation and sequence next-ID safety |
| `scripts/recovery_session.py` | Private owner-client stdin protocol that keeps the snapshot open without exposing rows |
| `scripts/recovery_drill.py` | Explicit separate-cluster guard, private custom backup, fresh restricted database creation, owner restore, DDL reparse/data equality and owned-helper cleanup |
| `tests/test_recovery.py` | Seventeen meaningful guard/failure/private-output/PostgreSQL snapshot/data/sequence tests |
| `compose.yaml`, `compose.worker.yaml`, `config/settings/base.py`, `scripts/verify_curl.py` | Current image/API label 1.4.0; existing defaults/worker activation rules retained |
| `README.md`, `docs/api.md`, `docs/getting-started.md`, `docs/architecture.md` | Current capability/version links and recovery/update boundary |
| `docs/testing.md`, `docs/limitations.md`, `docs/portfolio.md` | Actual checks, private/global/sequence/recovery limits and technical presentation |
| `docs/recovery/design.md`, `operations.md`, `verification.md`, `review.md`, `changes.md` | Rules before code, safe operating instructions, actual commands/results, independent review and this inventory |
| `reports/recovery/focused-first.json`, `focused-final.json`, `source-setup.json` | Actual focused PostgreSQL checks and fictional six-state source preparation |
| `reports/recovery/demo-first.json`, `demo-final.json`, `olist-full.json` | Actual source/restored row/schema/migration/sequence and archive metadata for each trusted drill |
| `reports/recovery/source-preservation.json`, `private-artifact-checks.json`, `local-cleanup.json`, `local-provenance.json` | Independent source recapture, private modes/checksums/ignore coverage, retained resources and exact candidate reconstruction |
| `reports/recovery/local/*.json` | Six final disposable CI command/check/role/OpenAPI/schema/runtime artifacts |

Hosted artifacts/metadata are retained only after actual execution. No application model/migration/current SQL schema, historical importer/report or dated index measurement changes. Backups, manifests, schema captures, private envs/helpers/raw logs and restored row data remain outside Git.

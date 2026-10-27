# Continuous integration independent review

Outcome: **no unresolved material findings; local and hosted evidence reviewed, ready for the user's technical review**. The first code review preceded publication; the hosted review below followed actual execution.

Initial read-only review identified target-prefix propagation, shared image tags, Linux bind ownership and artifact boundaries as concrete hazards. The implementation addresses these with one controlled disposable workspace/Compose environment, a unique image, precreated host directories and a sanitized artifact allowlist.

The reviewer found a P2 guard bypass: host aliases/network mode and external additional build contexts could evade the stated isolation boundary. The driver now rejects unsupported network/DNS/shared-namespace options and build inputs/Dockerfiles outside the copied workspace. Adversarial probes and tests verify those refusals. No current application Compose configuration used those options.

## Independent checks actually completed

- Read the complete runner, workflow and seven new safety tests; targeted Ruff lint/format and staged/unstaged whitespace checks passed.
- Pure in-memory probes confirmed the original bypasses, then confirmed owned configuration is accepted and host aliases/networking, DNS/modified network, extra contexts and external Dockerfile variants are rejected.
- Official action commit identities match checkout v7.0.1 and upload-artifact v7.0.2. Workflow permissions, normal pull-request event, nonpersistent checkout credentials, exact artifact allowlist, seven-day retention and guarded cleanup were inspected.
- Retained local evidence consistently records nine successful phases, 137 PostgreSQL tests in 10.256 seconds, 75 role checks, 38 OpenAPI paths, unchanged schema/restoration and completed owned cleanup. The removed workspace is actually absent.
- The six published local artifacts are byte-identical to completed private outputs. Local source fingerprint provenance was independently reproduced: only README's later test-count paragraph changed among hashed inputs; retaining its already-present CI table row reproduces the original fingerprint exactly.

## Hosted artifact review

The reviewer independently checked [push run 40495339203](https://github.com/joaoltrevisan/django-orders-inventory-portfolio/actions/runs/40495339203) for exact revision `5db02152f50efd68c65ed0a4d420ac21bc07f1cf`:

- Run, event, job and every step succeeded, including cleanup and artifact upload; artifact metadata identifies the same run/revision.
- Exactly six allowlisted JSON files were downloaded; published copies match those bytes. A recomputed commit-tree snapshot hash matches the hosted summary.
- Nine phases and seven verification commands exited 0; 137 tests passed in 13.002 seconds and 75 role checks passed.
- OpenAPI has 38 paths/API 1.0.0; schema has 28 tables/20 migrations with successful restoration and matching hashes.
- Actual hosted runtime is PostgreSQL 17.11 / Python 3.12.15 / x86_64.
- Independent raw-log/artifact scans found no matching known local secrets or JWT/GitHub-token-shaped values.

The reviewer ran no Docker/database jobs, suites or hosted workflows and changed no files. Current local Docker-resource state was not checked because the daemon was unavailable during the resumed handoff. The original artifact ZIP was unavailable for an independent archive-digest recomputation; the API-reported digest and metadata were inspected. Deleted hosted credential values were unavailable for exact-value scanning. One push execution is verified; pull-request/manual execution was not separately tested. Final documentation publication can trigger a later, separately checked run.

# Continuous integration independent review

Outcome before first publication: **no unresolved material code findings; ready to publish the workflow and collect hosted evidence**. GitHub execution remains a separate verification step.

Initial read-only review identified target-prefix propagation, shared image tags, Linux bind ownership and artifact boundaries as concrete hazards. The implementation addresses these with one controlled disposable workspace/Compose environment, a unique image, precreated host directories and a sanitized artifact allowlist.

The reviewer found a P2 guard bypass: host aliases/network mode and external additional build contexts could evade the stated isolation boundary. The driver now rejects unsupported network/DNS/shared-namespace options and build inputs/Dockerfiles outside the copied workspace. Adversarial probes and tests verify those refusals. No current application Compose configuration used those options.

## Independent checks actually completed

- Read the complete runner, workflow and seven new safety tests; targeted Ruff lint/format and staged/unstaged whitespace checks passed.
- Pure in-memory probes confirmed the original bypasses, then confirmed owned configuration is accepted and host aliases/networking, DNS/modified network, extra contexts and external Dockerfile variants are rejected.
- Official action commit identities match checkout v7.0.1 and upload-artifact v7.0.2. Workflow permissions, normal pull-request event, nonpersistent checkout credentials, exact artifact allowlist, seven-day retention and guarded cleanup were inspected.
- Retained local evidence consistently records nine successful phases, 137 PostgreSQL tests in 10.256 seconds, 75 role checks, 38 OpenAPI paths, unchanged schema/restoration and completed owned cleanup. The removed workspace is actually absent.
- The six published local artifacts are byte-identical to completed private outputs. Local source fingerprint provenance was independently reproduced: only README's later test-count paragraph changed among hashed inputs; retaining its already-present CI table row reproduces the original fingerprint exactly.

The reviewer ran no Docker/database jobs, suites or hosted workflows and changed no files. Current Docker-resource state was not checked because the daemon was unavailable during the resumed handoff. Hosted results and their artifact review will be recorded after actual execution.

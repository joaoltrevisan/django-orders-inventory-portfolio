# Continuous integration delivery verification

This extends the six completed stages from clean commit `6023973`. Inspection found no existing `.github` configuration; GitHub Actions is enabled for the public repository. Existing application, datasets, business rules and dated query measurements are preserved.

The reusable runner, workflow and adversarial isolation tests were implemented before publication. Official action release references were queried directly and pinned by full commit SHA. Independent review covers target propagation, private credentials, Linux mount ownership, unique image identity, output redaction, cleanup scope and actual hosted evidence.

## Initial local preflight corrections

The first preflight rejected Compose's added empty `ipam` metadata. The second revealed that resolved configuration omits profiled services unless the tools profile is explicitly selected. Both failures occurred before resource provisioning. The driver now accepts only empty/default IPAM and explicitly propagates the complete tools profile to all subprocesses, while retaining strict resource ownership checks. Neither attempt modified the existing service environment.

## Executed outcomes

The final local command was:

```bash
python3 -m scripts.run_ci --output .local/ci-validation/final
```

It completed all nine phases with exit 0: build, PostgreSQL startup, migrations, grants, seven-command verification, empty-history role probe, strict OpenAPI, schema restoration and runtime capture. **137 PostgreSQL tests passed in 10.256 seconds**. Seven new adversarial safety tests cover existing-resource boundaries, network/build inputs, inherited environment overrides, forged cleanup targets, tracked-only snapshotting and secret redaction.

[Local commands/output](../../reports/ci/local/summary.json), [test results](../../reports/ci/local/checks.json), [role checks](../../reports/ci/local/roles.json), [schema evidence](../../reports/ci/local/schema.json) and [runtime](../../reports/ci/local/runtime.json) are actual retained results. Strict OpenAPI produced 38 paths and schema restoration confirmed the unchanged 28 tables / 20 migrations. [Cleanup evidence](../../reports/ci/local-cleanup.json) confirms the invocation's workspace, volume/network and image tag were removed; the existing Stage 6 image and earlier data volumes were preserved.

Independent review identified configuration-guard bypasses through host aliases/host networking and additional external build contexts. The driver now rejects those options and Dockerfiles outside the copied workspace; adversarial cases were added and the full local pipeline rerun. Initial preflight failures remain in [first](../../reports/ci/preflight-first.json) and [second](../../reports/ci/preflight-second.json) evidence rather than being presented as successes.

After the local run, README's test-count paragraph was updated while its CI table row already existed. [Provenance reconstruction](../../reports/ci/local-provenance.json) reproduces the retained input fingerprint exactly with that README version; no runtime code changed after the successful run. Documentation/report files under their respective directories are excluded from this fingerprint.

On resuming the handoff, the local Docker daemon was unavailable. The earlier resource-preservation observations and completed local results are retained as dated evidence, not presented as a fresh health probe. The dated Stage 5 index experiment is not rerun by CI.

## Actual GitHub Actions execution

Publishing workflow commit `5db02152f50efd68c65ed0a4d420ac21bc07f1cf` automatically triggered a **push** run on 2026-10-27: [run 40495339203](https://github.com/joaoltrevisan/django-orders-inventory-portfolio/actions/runs/40495339203). It completed successfully, including the cleanup retry and artifact upload. [Run metadata](../../reports/ci/github-run.json) records the exact revision/event, job/step outcomes and timestamps; [artifact metadata](../../reports/ci/github-artifacts.json) records the uploaded archive identity, size, digest and expiration.

The downloaded archive contained exactly the six allowlisted public JSON files. All nine driver phases and all seven verification commands exited 0. **137 PostgreSQL tests passed in 13.002 seconds**, **75 role checks passed**, strict OpenAPI retained **38 paths**, and schema restoration confirmed **28 tables / 20 migrations** with the committed SQL file hash. Actual hosted runtime was **Python 3.12.15 / PostgreSQL 17.11 on x86_64**. [Hosted summary](../../reports/ci/github/summary.json), [checks](../../reports/ci/github/checks.json), [roles](../../reports/ci/github/roles.json), [OpenAPI](../../reports/ci/github/openapi.json), [schema](../../reports/ci/github/schema.json) and [runtime](../../reports/ci/github/runtime.json) are byte-for-byte downloaded artifacts, not manually synthesized results.

The hosted source-input hash matched the tracked revision's current inputs before the later README badge/documentation update. Local and hosted durations belong to different environments and are not a performance comparison. Raw hosted logs stay ignored locally; [log review](../../reports/ci/github-log-review.json) found no configured local-secret values or JWT/GitHub-token-shaped values. Hosted ephemeral passwords were deleted with the workspace, so their exact values are not independently available for a later scan. Redaction and the narrow upload allowlist are enforced by the driver/workflow.

The successful event tested here is push-to-main. Pull-request/manual triggers are configured but were not separately exercised. No branch-protection requirement, deployment or registry publication was configured. The workflow uses temporary test data and never downloads the real Olist archive or reruns the index experiment. Final documentation publication may trigger an additional run; the immutable evidence above refers specifically to the first successful workflow revision.

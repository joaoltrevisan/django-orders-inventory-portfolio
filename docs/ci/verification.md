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

On resuming the handoff, the local Docker daemon was unavailable. The earlier resource-preservation observations and completed local results are retained as dated evidence, not presented as a fresh health probe. Hosted results will be recorded after actual completion; no GitHub CI success is inferred from YAML or local checks alone. The dated Stage 5 index experiment is not rerun by CI.

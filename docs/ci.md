# Continuous integration

[PostgreSQL verification](https://github.com/joaoltrevisan/django-orders-inventory-portfolio/actions/workflows/ci.yml) runs on pushes to `main`, pull requests and manual dispatch. It extends the six completed implementation stages with repeatable hosted validation. No deployment, registry publishing or historical-data download is performed.

## What runs

The Ubuntu 24.04 job executes `python3 -m scripts.run_ci --output ci-results`. The same driver can be run locally with Python 3.11+, Docker/Compose and Git:

```bash
python3 -m scripts.run_ci --output .local/ci-validation/new-run
```

Choose a new output directory. The driver copies **tracked working-tree files**, including modifications, into an exclusively created private workspace. Stage new source files with `git add` before local validation; untracked files, repository credentials and local data are not copied. Staging does not require committing before verification. A source-input fingerprint records the checked snapshot, excluding the `docs` and `reports` directories.

The pipeline builds a uniquely tagged application image and starts only a new PostgreSQL instance. It applies migrations/grants, then executes:

1. Existing seven-command dependency/lint/format/Django/migration/PostgreSQL test verification.
2. The empty-history database-role probe, before any source import; its rollback/empty-target guards remain active.
3. Strict OpenAPI generation with validation and warnings treated as errors.
4. Migration-consistent schema export and restoration checks in disposable databases.
5. Actual Python/package/PostgreSQL runtime metadata.

No web container or host port is started. Automated fictional fixtures are used in test databases. The full Olist import, historical SQL outputs and dated index experiment remain separate evidence, not workloads rerun on every commit.

## Isolation and cleanup

Each invocation allocates `olist-ci-<random hex>`, database `olist_ci`, its own named volume/network and `olist-ci-app:<project>` image. It generates mode-0600 credentials only in the copied private workspace. All child processes, including older verification helpers, receive the same controlled Compose file/project/env/profile selection. Inherited Compose overrides and exported local database credentials cannot redirect the run.

Before provisioning or cleanup, the resolved private configuration is checked for the expected project, owned nonexternal volume/network, unique application image, internal database connection, local build context and workspace-contained bind mounts. Existing resources under the new allocation cause refusal. Host-owned bind directories are created first, and verification output is captured on the host to avoid Linux/container UID mismatch.

The driver uses `finally` cleanup and the workflow has an `always()` guarded retry. Only that invocation's validated resources are removed, including its disposable volume and image tag. This is not a command to delete existing service data. A retained `cleanup-state.json` supports a targeted retry:

```bash
python3 -m scripts.run_ci --cleanup .local/ci-validation/new-run/cleanup-state.json
```

Normal cleanup deletes the temporary workspace and its credentials. Forced process termination or runner loss can prevent finalizers; hosted runners are ephemeral, while a local interrupted run may need the guarded retry. No global Docker pruning or default-project fallback is used. Failure artifacts remain available without resetting or overwriting an earlier result directory.

## Permissions and artifacts

The workflow grants only `contents: read`, uses normal `pull_request` events, and disables checkout credential persistence. Official checkout v7.0.1 and upload-artifact v7.0.2 are pinned to verified full commit SHAs. This follows [GitHub's secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use); action release identity is documented by [checkout releases](https://github.com/actions/checkout/releases/tag/v7.0.1) and [artifact releases](https://github.com/actions/upload-artifact/releases/tag/v7.0.2). Hosted Ubuntu software is maintained separately; actual runtime versions are captured rather than inferred from the runner label.

Only `summary.json`, `checks.json`, `roles.json`, `openapi.json`, `schema.json` and `runtime.json` are uploaded, with seven-day retention. Command outputs and files have generated credential values redacted before publication. The workflow never uploads `.env`, private workspace/state, resolved Compose configuration, source archives or unrestricted container logs. Artifact behavior follows the [official action documentation](https://github.com/actions/upload-artifact). Logs/artifacts are evidence of the particular revision/run; passing CI is not production certification or a new performance result.

Concurrency cancellation supersedes older runs on the same ref; a 20-minute timeout bounds jobs. First-time fork jobs may require GitHub's normal approval. Branch protection/required-check settings are not changed by adding this workflow. [Delivery verification](ci/verification.md), [independent review](ci/review.md) and [file inventory](ci/changes.md) record actual local/hosted outcomes and limits.

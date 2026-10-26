# Independent review process

Every development stage must receive an independent review before its final handoff. The implementer and reviewer have separate responsibilities. All committed review notes, findings, corrections, and commit messages must be English; explanations to the user remain Brazilian Portuguese.

## Workflow

1. The implementer completes the authorized stage and runs the checks appropriate to the changes. Record actual commands, results, and unavailable checks.
2. An independent reviewer inspects the requirements, final changes, tests, and evidence. The reviewer may perform read-only checks and must report actionable findings with file/line references, impact, and priority. The reviewer must distinguish a design proposal from implemented behavior and measured evidence.
3. The implementer addresses findings, records the resolution, and reruns affected checks. Correctness, integrity, authorization, data-loss, and unsupported evidence claims must be resolved before declaring the stage ready. Escalate requirement conflicts to the user before implementing affected behavior.
4. The reviewer verifies material corrections. Record remaining limitations honestly; do not imply that review proves the absence of defects.
5. Publish coherent incremental English commits and a stage review record. Present decisions, files, actual verification results, findings/resolutions, and outstanding work to the user in Brazilian Portuguese.
6. Stop for the user's technical review. An independent review, a passing check, or a pushed commit does not authorize the next stage by itself.

## Review focus

| Stage | Primary concerns |
| --- | --- |
| 1 / Olist adaptation | Requirements consistency, source profiling/license, historical-versus-simulated facts, business rules, permissions, relational design, integrity boundaries, and realistic verification plans |
| 2 | Supported dependencies, isolated PostgreSQL/roles, source timestamp preservation, seller-offer models, migration/schema agreement, constraints, indexes, and preservation of existing work |
| 3 | Repeatable historical import and reconciliation, no-op/rollback behavior, read-only historical permissions, authentication, English responses, owner isolation, administrative permissions, and pagination |
| 4 | Multi-seller atomic writes, offer-level lock ordering/stock, overselling prevention, purchase snapshots, ledger integrity, cancellation idempotency, and controlled concurrency tests |
| 5 | Imported-data isolation, Olist SQL grain/correctness, identical before/after inputs, new plans and individual measurements, medians, storage/buffer evidence, and honest conclusions |
| 6 | Accurate English documentation, reproducible workflows, OpenAPI consistency, test evidence, portfolio clarity, and disclosed limitations |

Review findings should prioritize demonstrated defects and concrete risks rather than speculative rewrites or stylistic preferences. A reviewer must never report unexecuted tests as passing. Secrets, tokens, and private database data must not appear in review artifacts.

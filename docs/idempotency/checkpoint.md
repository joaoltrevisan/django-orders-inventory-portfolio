# Archived pause checkpoint

**Historical checkpoint:** resumed on 2026-10-27. The text below records the earlier pause, not current delivery status. See [verification](verification.md) for completed work and remaining limits.

Paused at the user's explicit request on 2026-10-27. Resume from this checkpoint; do not start another feature.

## Saved implementation

Base published revision: `a761a9c` (verified GitHub CI). Work is saved on local branch `codex/order-idempotency-checkpoint`; this unfinished feature is not published.

The [contract](design.md) defines optional customer-scoped `Idempotency-Key`, canonical validated content, 201 creation / 200 replay, conflict handling, retained keys and failed-attempt rollback. Code adds nullable SHA-256 fields, a null-safe pair CHECK and scoped partial uniqueness to Order; a transaction advisory lock precedes the existing lock hierarchy. Replay rechecks the current customer, locks/inspects the existing order and returns cached snapshots without reserving again. Unkeyed callers retain their interface and behavior. OpenAPI annotations and the API/image version were updated to 1.1.0.

Independent initial implementation review found no material defects after pure/static checks. Full execution-evidence review remains outstanding.

## Actual completed verification

- Ruff checks passed for changed order code, coordination helper, migration and tests.
- A fresh isolated `olist-idempotency-review` Compose project was created with private `.local/idempotency/review.env`, database `olist_demo`, port reserved at 18026 and its own named volume. Existing primary/benchmark/demo/legacy data was not targeted.
- The previous Stage 6 image applied 20 migrations and seeded five fictional orders. [Baseline hashes](../../reports/idempotency/before-migration.json) and [setup commands](../../reports/idempotency/baseline-setup.json) are retained without row-level credentials.
- Django generated `orders/migrations/0002_creation_idempotency.py`. The new 1.1.0 image applied it in the isolated database and reapplied grants.
- **20 focused PostgreSQL tests passed in 1.000 second**, including five controlled separate-connection lock-contention scenarios. The disposable test database was destroyed normally. [Exact commands/output](../../reports/idempotency/focused-checks.json) record all three exit codes as 0.

The review database is stopped gracefully for this pause; its volume, private configuration and data are retained. No tests, builds or verification commands remain running.

## Required work when resumed

1. Restart only the isolated review database, capture its post-migration data hashes, and compare all old fields/rows with the baseline. Verify the five old orders have both new fields NULL.
2. Export a new candidate schema from that migrated isolated database using a controlled Compose project/env selection. Review and update `sql/schema.sql`; it still reflects the previous schema at this checkpoint. **Current CI is not ready to publish until this is corrected.**
3. Run the complete PostgreSQL suite, strict OpenAPI, migration drift/applied checks and schema restoration. The complete suite has not yet been run for this feature; do not infer its count/result from the focused run.
4. Verify actual HTTP/curl creation, replay, conflict, cancellation replay and authorization in the isolated environment. Update the current API/architecture/ER/limitations/README guides and add a reproducible key example. Earlier stage evidence remains historical.
5. Complete independent review, retained evidence/file inventory, and actual hosted CI before publishing this feature. Preserve the existing databases and images throughout.

Local resume command for the preserved database:

```bash
docker compose -p olist-idempotency-review --env-file .local/idempotency/review.env up -d --wait db
```

Do not reseed, reset, remove its volume, or overwrite existing evidence files. Reservation expiry and other enhancements remain outside this delivery.

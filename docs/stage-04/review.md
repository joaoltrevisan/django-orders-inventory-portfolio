# Stage 4: independent review

Date: 2026-10-26. Outcome: **no unresolved material findings; ready for the user's technical review**. Stage 5 remains a separate approval checkpoint.

## Scope and decisions reviewed

The independent reviewer inspected the operational rules, shared offer locking, inventory/ledger/headroom services, order creation/integrity/lifecycle/selectors/validation, HTTP serializers/views/routes, current permissions, error handler, fixtures and coordinated concurrency tests. Final review also covered the API/verification guides, README/ER status updates and actual retained execution artifacts.

Offer-level reservations, ordered parent/offer/stock locking, server totals/snapshots, atomic writes, owner-scoped lookups, current authorization, actual cancellation actors and coherent action snapshots match the approved contract. Pending-liability aggregation takes no inverse order locks. Administrative cancellation preserves inactive customers/catalog history, and past actor roles are not reconstructed from current staff flags. Conservative parent lock granularity and no-real-payment boundaries are documented.

The implementer's strict OpenAPI check discovered an adapter attribute-name collision: APIView's callable `action` interfered with schema introspection expecting a ViewSet action-name string. It was renamed `transition`; the reviewer confirmed the correction, and the implementer rebuilt and reran the complete tests and strict schema validation successfully. No other material defect remained after review.

## Independent read-only checks actually executed

| Check | Result |
| --- | --- |
| Ruff lint and formatting | Passed; final reviewer run reported 120 Python files already formatted |
| Tracked diff and supplemental untracked whitespace checks | Passed; 34 untracked files checked at review time |
| Markdown links/fences | 26 documents; 91 resolved local links at review time |
| Final consolidated test evidence | Seven command exit codes 0; 106 tests completed in 7.995 seconds |
| Concurrency extraction versus final stdout | Exact match; 15 distinct scenarios with separate backend PIDs and actual PostgreSQL blocking |
| HTTP evidence | 47 expected statuses; purchase snapshot/repetition/admin-cancellation assertions passed |
| Strict OpenAPI evidence | 37 paths; exit 0 |
| Runtime evidence | Matching recorded image IDs; nonroot `app`; HTTP 200 Stage 4 health |
| Operational reconciliation/counts | Balances 0/8/4 equal ledger totals; totals 91.80/100.00/30.00 match items; 3 orders, 5 items, 1 payment, 1 shipment, 12 movements |
| Historical preservation | Full local report hash matches published summary; NOOP verifies 451,537 entities; 99,441 source orders retained |
| SQL schema evidence | File/normalized hashes match; restoration flags true; unchanged 28 tables and 20 migrations |
| Legacy checkout | Clean at `21b5b17` |

The reviewer initially misinterpreted Git's ordinary no-index difference exit code in a supplemental whitespace-check script; the corrected diagnostic check passed. This was a reviewer harness correction, not a repository defect.

The reviewer **inspected retained execution evidence**, rather than independently rerunning PostgreSQL suites, HTTP workflows, Docker operations or restoration. No review edits, commits or database mutations occurred. This review record and the [file inventory](changes.md) were added afterward; the implementer checks their links and staged diff before publication.

## Remaining limits

Review does not establish production readiness, absence of all possible deadlocks/schedules, real payment/carrier integrations or performance gains. Mermaid rendering remains unverified. The repeatable simulated seed command, Olist SQL business-query collection and fresh index experiment remain Stage 5 work. Final portfolio/documentation polish remains Stage 6. See [verification](verification.md) for actual commands/results and [rules](rules.md) for the precise implemented service boundaries.

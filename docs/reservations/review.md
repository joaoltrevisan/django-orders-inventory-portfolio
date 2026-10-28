# Independent reservation expiry review

The reviewer inspected the existing lifecycle, creation keys, inventory headroom and schema before implementation, then approved the written deadline/explicit-expiry contract. Review was read-only; no database mutation or Docker workload was run by the reviewer.

The initial implementation review found one concrete mismatch: the command accepted both API and test database roles although its contract required the API role. Production now accepts only `olist_api`; a real test-role refusal is asserted, successful service-delegation tests mock only the target-identity guard, and real CLI execution through the API role verifies the authorized path.

The reviewer checked one-order transactions, commit-before-success reporting, exclusion of attempted IDs, partial-failure progress, current authorization after stock-lock waits, wall-clock decisions after waits, NULL legacy compatibility, null-safe temporal/status CHECKs, EXPIRED handling in payment/history/replay and continued pending-stock liability. Eight new races coordinate separate PostgreSQL connections: five observed blocking schedules and three SKIP LOCKED schedules. No other material implementation defect was found in that pass. Ruff and whitespace checks passed.

The HTTP runner's source-free/API-role/loopback/dedicated-project checks and explicit time shift restricted to a new owned unprocessed fixture were reviewed. The reviewer recommended verifying the exact owner-refusal message rather than any exit 1; this was implemented and the 16-request/three-command workflow rerun successfully. The inherited `hash_columns` metadata name is explained in verification without rewriting original artifacts. Final complete-suite/HTTP/schema evidence review and actual hosted results are recorded below when completed.

## Completed local evidence review

The final reviewer independently verified nine successful phases/seven successful commands, **184 tests in 12.607 seconds**, 25 observed blocking records/three SKIP LOCKED records and normal test-database destruction. Role checks total 75. OpenAPI is API 1.2.0/38 paths with nullable read-only deadline/expiry fields and payment 200/409. Current SQL SHA matches the schema artifact: 28 tables/22 migrations. The current runtime/SQL inputs plus the run's README reconstruct the source fingerprint exactly.

All 23 domain table hashes and five legacy NULL pairs match before/after migration. General curl passed 50 requests; both expiry invocations passed 16 requests/three CLI checks, with the final report explicitly verifying the role-guard message. Current-document relative links resolve. No inspected configured local secret or JWT/GitHub-token/private-key pattern was found in new JSON evidence. Initial failures are retained and explained. No material blocker remained; the reviewer approved local publication conditional on recording this decision and checking actual hosted CI. This was a read-only review, without Docker/database reruns by the reviewer.

## Completed hosted evidence review

The reviewer independently approved successful push run **40623871962** for exact revision `b57265dc72136ffba04ca3680a47e53a7d549500` (created 2026-10-28T02:56:55Z UTC). All nine phases/seven commands exited 0; **184 tests passed in 25.764 seconds**, with 25 blocking records/three SKIP LOCKED records and normal test-database destruction. There were 75 role checks; API 1.2.0/38 paths; 28 tables/22 migrations; Python 3.12.15 on x86_64.

The source-input hash reconstructed from the Git revision and the exact current SQL hash match the hosted evidence. The six published JSON files match the private download byte-for-byte and artifact metadata identifies the same revision. Inspection of raw private logs and JSON found none of the inspected local configured secrets or JWT/GitHub-token/private-key patterns. Deleted ephemeral hosted secrets remain unavailable for a later exact-value check, as disclosed. Whitespace validation passed and no material blocker remained. The evidence-only commit is authorized for publication; its automatically triggered CI is checked separately from these immutable artifacts.

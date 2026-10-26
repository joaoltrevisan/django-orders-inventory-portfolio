# Stage 4: executed verification

Date: 2026-10-26. Scope: multi-seller order creation, inventory audit/headroom, cancellation, simulated lifecycle, permissions, safe errors and controlled PostgreSQL contention. Historical imports, authentication and catalog behavior from earlier stages remain covered by the full suite. No Olist historical fact is converted into operational inventory or authentication.

## Executed commands and retained results

| Command/check | Actual outcome |
| --- | --- |
| `docker compose build app` | Stage 4 image built successfully |
| `python3 scripts/verify_stage2.py --output reports/stage-04/checks.json` | All seven commands exit 0; **106 PostgreSQL tests passed in 7.995 seconds**; pip, Ruff, Django checks, migration drift/applied-state checks passed |
| Controlled transaction tests within that suite | **15 distinct scenarios** observed real PostgreSQL blocking between separate backend PIDs; no arbitrary-delay-only coordination |
| `docker compose run --rm migrate spectacular --format openapi-json --validate --fail-on-warn` | Exit 0; **37 paths**, no warnings after the adapter correction |
| `docker compose up -d --wait app` and actual local HTTP client | Healthy; **47 requests** matched expected statuses and business assertions |
| `python3 scripts/database_schema.py verify --report reports/stage-04/schema-verification.json` | Export/live/isolated-restoration agreement; unchanged **28 tables and 20 migrations** |
| Restricted importer `import_olist ... --report /reports/stage4-preservation-noop.json` after operational HTTP writes | `NOOP`; **451,537 complete historical entities verified/skipped**, zero historical inserts/rejections/duplicates |
| Runtime and read-only SQL probes through `olist_api` | Built/running images match, nonroot `app`, HTTP 200 Stage 4; decimal order totals and all current stock balances reconcile |

The shared verifier retains its Stage 2 filename but executes the current complete suite. Repeat without overwriting published evidence:

```bash
python3 scripts/verify_stage2.py --output .local/stage-04/checks-new.json
```

Tests create/destroy only a disposable PostgreSQL test database through `olist_test`. They do not reset the imported application database. The final [checks artifact](../../reports/stage-04/checks.json) retains all actual commands, outputs, exit codes and the completed test log. Earlier successful 106-test evidence before the schema-name fix remains local; the published artifact describes the final code/image. Production password hashing is unchanged; only non-authentication concurrency fixtures select a fast test-only hasher. Real HTTP demonstration accounts keep Django-hashed private random passwords.

## Correctness and transaction coverage

New checks cover one product purchased from two sellers, 1–100 distinct offers, strict integer quantities, protected inputs, server totals and snapshot labels/prices, missing/inactive parents or uninitialized inventory, owner isolation with distinct User/Customer keys, stock entries/adjustments, capacity headroom, ledger reconciliation, administrator cancellation and role changes, cancellation repetition, complete lifecycle/repetition/tracking conflicts, corrupted cross-table history, and safe database-error responses.

Fault injection occurs **after a real ledger INSERT** and after cancellation status writes, proving rollback of order/items, stock and movements rather than merely failing preflight validation. Other tests cover payment-associated write failure and inventory movement failure. Missing/contradictory history fails without repair, including on repeated actions.

Contention scenarios use `TransactionTestCase`, separate connections/PIDs, events, ordered row locks and a third observing connection. The helper calls `pg_blocking_pids(second_pid)` before releasing the first operation; short bounded polling observes an actual wait. Worker timeouts prevent indefinitely hung tests. [concurrency.json](../../reports/stage-04/concurrency.json) extracts the actual final test stdout observations:

1. Last unit bought once; waiting buyer sees insufficient stock.
2. Reversed multi-seller/multi-product inputs finish in common lock order.
3. Failed first reservation rolls back and waiting buyer can purchase.
4. Double cancellation restores once and retains the first actor/timestamp.
5. Payment first blocks and defeats cancellation.
6. Cancellation first blocks and defeats payment.
7. Simultaneous payment confirmations preserve one reference.
8. Shipping followed by waiting delivery returns coherent action snapshots.
9. Repricing first makes waiting purchase use the committed new price.
10. Purchase first retains old snapshots while repricing waits.
11. Seller deactivation first prevents waiting purchase.
12. Concurrent adjustments accumulate without a lost update.
13. Inventory reduction first forces waiting purchase to recheck balance.
14. Different orders cancel overlapping offers without inverse order locks.
15. A test-only stock-row probe confirms purchase explicitly waits on `inventory_stock ... FOR UPDATE` before deducting.

The stock-row probe performs no writes or later parent acquisition; it is deliberately not a production service lock pattern. Passing these bounded scenarios does not prove every possible schedule or high-load throughput. Parent locks conservatively serialize even some otherwise unrelated offers sharing a seller/product; this favors clear consistency over maximal concurrency. No throughput gain is claimed.

## Actual HTTP and database state

The local workflow used fictional identities and two new simulated offers for the same product from different sellers. Initial supply was 10/5 units at current simulated prices 25.90/40.00. The first purchase of quantities 2/1 totaled **91.80** and retained its original price/name/seller snapshots after repricing/renaming. Owner cancellation and repetition restored once. A second purchase used the new first-offer price 30.00 and total **100.00**, then progressed through simulated payment, shipping and delivery; repetitions preserved records/timestamps. A third one-unit order totaled **30.00**; an administrator cancelled it while its buyer was inactive, recording the administrator as release actor. The customer was reactivated afterward.

Explicit adjustment -1 followed by entry +1 demonstrated append-only correction without a lasting balance change. An insufficient-stock purchase returned 409 without another order. Ending available balances were **8 and 4**. The pre-existing Stage 3 offer remains at zero. Separate SQL aggregation from the zero initial balances reconciled every stock row with its signed movement total; item subtotals matched all three server order totals. The current operational domain has three orders (two cancelled, one delivered), five items, one simulated payment/shipment, and twelve stock movements. These are fictional workflow results, not Olist historical sales or inventory facts.

Source order count remained **99,441** during HTTP verification; the subsequent full content no-op also verified every mapped historical field/relationship and provenance. Only a new no-op attempt/issue audit record is added; historical facts are unchanged. Published artifacts exclude passwords, JWTs, full addresses and raw source archives.

## Evidence and corrections

Evidence: [checks](../../reports/stage-04/checks.json), [contention observations](../../reports/stage-04/concurrency.json), [HTTP statuses/assertions](../../reports/stage-04/http.json), [operational SQL/results](../../reports/stage-04/database.json), [runtime](../../reports/stage-04/runtime.json), [schema agreement](../../reports/stage-04/schema-verification.json), [OpenAPI verification](../../reports/stage-04/openapi-verification.json), [historical preservation](../../reports/stage-04/historical-preservation.json), and its [actual command](../../reports/stage-04/historical-preservation-command.json). The preservation summary omits full source-key issue lists/individual deltas, retaining their local report hash and aggregate counts.

Initial formatting/lint issues were corrected before the successful suite. The first strict schema generation failed because an APIView callable named `action` collided with drf-spectacular's expected ViewSet action-name string. Renamed that adapter attribute to `transition`, rebuilt, reran the full 106-test suite and strict schema generation; both passed. No failed check is being reported as a pass.

Models, constraints, migrations, dependency pins and the SQL export required no change. The legacy checkout remains clean at `21b5b17`; its database/containers/volume were not migrated, replaced, flushed or removed. The existing isolated app database was extended through authorized API operations; no old data was reset.

Remaining work: repeatable fictional seed generation, the Olist SQL business-query portfolio and a newly measured index experiment, then final documentation/presentation. No real payment/carrier integration, reservation expiry, creation idempotency keys, partial seller processing, production hosting or performance benchmark is claimed. Privileged SQL can bypass application invariants. Stop for user technical review before Stage 5.

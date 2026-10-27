# Delivered-order page: index experiment

Executed 2026-10-26 on PostgreSQL **17.11**, Python **3.12.15**, Django **5.2.18**, psycopg **3.3.6**, aarch64 Docker runtime. The database is the separate `olist-benchmark` project / `olist_benchmark` database / `olist-benchmark_olist_postgres_data` volume. It contains the accepted real Olist historical snapshot, including **99,441 orders**, **99,441 customer references**, **112,650 items** and **103,886 payment records**; all simulated operational tables are empty. No source rows were inflated or invented. [Runtime/isolation evidence](../../reports/stage-05/runtime.json) and [benchmark counts/fingerprints](../../reports/stage-05/benchmark-database.json) identify the environment.

## Query and hypothesis

The [frozen SQL](../../sql/olist/benchmark_delivered_page.sql) retrieves the first **100** delivered-order references in `[2017-11-01 00:00:00, 2017-12-01 00:00:00)`, ordered by timezone-free source purchase timestamp and source order ID, joining the repeat-customer identity through the source customer FK. Its status rule and source-calendar meaning are identical in every phase. A completed snapshot is required. This is a realistic administrative history-page shape, not a claim that the existing default order-list endpoint runs this exact SQL.

Candidate:

```sql
CREATE INDEX olist_bench_delivered_purchase_idx
ON olist_order (purchased_at_source, source_order_id)
INCLUDE (customer_id, snapshot_id)
WHERE source_status='delivered';
```

The partial predicate may reduce the relevant index scope; the date/order keys may avoid scanning and sorting the full order table to produce one small page. Included customer/snapshot FKs may permit an index-only order scan. These were hypotheses before execution; the existing baseline indexes were inspected and retained. No primary/unique/FK-supporting index was removed, and sequential scans were not disabled.

## Protocol and preserved evidence

The owner command first requires explicit enablement, literal expected database `olist_benchmark`, actual owner role, a completed accepted source and no simulated rows. It reserves a new output directory, serializes benchmark attempts, refuses an existing candidate name and recalculates complete natural-key/field fingerprints.

It performs `VACUUM (ANALYZE)` on orders, customers and the snapshot outside a transaction, then keeps the facts and manually refreshed table statistics unchanged across phases. It issues no further ANALYZE after CREATE/DROP because facts do not change. Psycopg automatic preparation is disabled for this connection so a preparation-threshold crossing does not distinguish phases.

Phases are **baseline → temporary index → control baseline after dropping the index**. Each has **3 warm-up runs and 7 measured runs**, all using `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, identical SQL/parameters and ordered-result hashing. All **30 actual plans** are retained, including warm-ups. No measured sample was discarded. The [summary](../../reports/stage-05/index-experiment/summary.json) records exact query/data/result fingerprints, settings, existing indexes, individual server execution/planning times, client round-trip times, buffers, index size/build time and final cleanup state. The [actual invocation](../../reports/stage-05/benchmark-command.json) exited 0.

## Measurements

Times below are PostgreSQL **Execution Time**, in milliseconds; planning and client time are separate in the artifact.

| Run | Baseline | Indexed | Control baseline |
| --- | ---: | ---: | ---: |
| 1 | 5.251 | 0.080 | 5.328 |
| 2 | 5.434 | 0.080 | 5.113 |
| 3 | 5.356 | 0.079 | 5.031 |
| 4 | 5.247 | 0.084 | 5.135 |
| 5 | 5.289 | 0.087 | 5.111 |
| 6 | 5.565 | 0.080 | 5.161 |
| 7 | 5.391 | 0.080 | 5.184 |
| **Median** | **5.356** | **0.080** | **5.135** |

Median planning times were **0.080 / 0.052 / 0.081 ms**. Median client times were approximately **5.765 / 0.363 / 5.476 ms**; the server execution result is therefore not an HTTP latency or network speedup promise. The later control is slightly faster than the first baseline, illustrating phase-order/cache/scheduling variation, while remaining much slower than the indexed phase for this query.

## Plan and buffer interpretation

The [first measured baseline](../../reports/stage-05/index-experiment/baseline-measured-01.json) uses a parallel order-table sequential scan, worker sorts (`quicksort` in the retained plan), `Gather Merge`, and 100 customer primary-key lookups through a nested loop. The limit consumes the first 100 ordered matches. Node row counts under multiple loops/workers must not be treated as a single exact marketplace count.

The [first indexed plan](../../reports/stage-05/index-experiment/indexed-measured-01.json) uses an **Index Only Scan** on the candidate to produce 100 ordered order references, then the same 100 customer PK lookups. No order-stream sort is needed. It records **0 heap fetches** for that order scan after vacuum visibility preparation. The tiny snapshot-table sequential scan remains appropriate; the result is not "all sequential scans eliminated."

Root-plan execution counters were **3,492 shared block hits** in every measured baseline/control and **306** in every measured indexed run. All measured phases report **0 shared read blocks** and **0 temporary blocks written**. These are reported block-access counters, not distinct pages or physical-disk throughput. Inclusive subtree counters must not be added across parents/children. The plans explain the smaller cached-data work; there is no cold-disk measurement.

## Storage, equivalence and limitations

The candidate occupied **8,282,112 bytes (7.90 MiB)**. The original order heap was **25,419,776 bytes** and its existing total relation storage **46,759,936 bytes**; the new index added about **17.71%** relative to that original total. Observed client index-build time was **35.450 ms**. This is additional storage and a future insert/update maintenance obligation; write amplification and concurrent index-build disruption were not benchmarked. Immutable historical rows and an order-history read shape differ from a busy mutable order-processing table.

All phases returned the same 100 rows with ordered SHA-256 `f9e64378ea7d2704eafcfdf5c7de7a1dcc1d090cc9fcd2f14c228a8b1d62cc05`. Complete source facts/relationships had equal before/after fingerprints. The temporary candidate was confirmed absent afterward; source/application schema and migrations were not changed. No old fictional-data timings are used as evidence.

Caches were deliberately **warm**: fingerprinting, initial reads, VACUUM, warm-ups and index construction all read data. New connections are not cold caches. The host/containers, background activity, EXPLAIN instrumentation, planner/statistical settings, sequential phase order and one fixed interval/page size limit generalization. Larger pages, different selectivity, mutable visibility maps, different hardware or competing workloads can choose different plans and produce different results. PostgreSQL was free to prefer a sequential scan; no improvement would have been a valid result.

For this measured query, the candidate helped. It remains an experimental candidate in the isolated benchmark, not an adopted production index or a global API speedup. Adopting it would require matching product access patterns, storage/write trade-offs and a separately reviewed migration. Reproduce the experiment with a fresh output directory using the [dataset/environment guide](datasets.md).

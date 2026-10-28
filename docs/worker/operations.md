# Running the optional reservation expiry worker

API/image 1.3.0 adds an opt-in periodic process around the existing expiry service. Default application/CI Compose remains five services and never starts this process. No package, table, migration, API route or Olist historical rule changes.

## Deliberate enablement

First build the current image, migrate, configure grants and provision an active administrator in the intended existing environment using the [execution guide](../getting-started.md). Preserve its env file and volume. In that private file deliberately set:

```dotenv
EXPIRY_EXPECTED_DATABASE=the-exact-existing-database-name
EXPIRY_ACTOR_EMAIL=an-existing-active-administrator@example.com
EXPIRY_INTERVAL_SECONDS=60
EXPIRY_BATCH_LIMIT=100
```

The committed env example contains placeholders; no account is automatically created. The worker uses `olist_api`, not schema ownership. Its actor is an explicit administrator account, not an inferred historical customer or fabricated system identity. Deactivation/staff revocation stops subsequent work after current authorization checks; existing committed history remains attributed to that account.

For a deliberately configured demo, consistently select its project/env and both Compose files:

```bash
docker compose -p olist-demo --env-file .local/analysis/demo.env \
  -f compose.yaml -f compose.worker.yaml --profile workers up -d expiry-worker
docker compose -p olist-demo --env-file .local/analysis/demo.env \
  -f compose.yaml -f compose.worker.yaml --profile workers logs --tail 20 expiry-worker
docker compose -p olist-demo --env-file .local/analysis/demo.env \
  -f compose.yaml -f compose.worker.yaml --profile workers stop expiry-worker
```

Substitute the actual project's configuration; do not enable scheduling on a populated environment unintentionally. The service has no published port/host mount, runs nonroot/read-only, uses Docker init for signal forwarding, `restart: "no"` and 30-second stop grace. It does not inherit the HTTP service's healthcheck. A fatal stopped container needs operator inspection and deliberate restart; no restart loop/alert is configured.

## Cycle, failure and shutdown contract

The first cycle starts immediately. After it completes, the process waits the configured interval (1–3600 seconds, default 60); there is no overlap/catch-up burst in one process. A cycle has a batch attempt limit of 1–1000, default 100. Multiple processes/manual invocations remain safe through existing per-order transactions and consistently ordered locks; neither an exclusive worker nor a complete sweep is promised.

Every cycle reconnects, reconfirms the exact database/`olist_api`, rereads the administrator and applies 5-second lock/15-second statement timeouts only to that connection. Batch stock/history failures retain earlier committed successes. Database failures produce sanitized `database_error` events and a delayed new cycle with fresh connection/authority checks. Invalid targets/roles/administrators and unexpected programming exceptions fail fast; exception text/DSNs are not logged. Corrupt oldest records can consume every attempt limit and starve later rows until intervention: no quarantine, repair or queue-fairness guarantee is included.

SIGTERM/SIGINT signal a stop event, interrupt interval waiting and prevent another order from starting. A release already in progress finishes its transaction; signal handlers are restored afterward. Timeouts limit individual statements, not total work. Docker may force termination after grace; PostgreSQL rolls back uncommitted transactions, while committed EXPIRED orders cannot release again. A graceful shutdown event does not mean all due work drained.

For bounded execution after configuring the same target:

```bash
docker compose -p olist-demo --env-file .local/analysis/demo.env \
  -f compose.yaml -f compose.worker.yaml --profile workers run --rm expiry-worker \
  run_reservation_expiry --expected-database olist_demo \
  --actor-email admin@example.com --interval-seconds 1 --max-cycles 2
```

`--max-cycles` accepts 1–10000; omission means unlimited and zero is rejected. Finite execution exits nonzero if its final cycle failed; a later successful recovery does not erase earlier failed events. A deliberate signal stop exits normally. Choose a currently active actor rather than blindly copying this seeded-demo email into another environment.

## Monitoring and backlog

Stdout contains JSON `worker_started`, `cycle_started`, `cycle_finished` and `worker_stopped` events. Cycle output records monotonic duration, outcome, aggregate batch counts/failure codes/stopped flag, and separate backlog observation. It does not contain tokens, passwords, addresses or raw SQL. Unavailable batch/metrics are NULL, never invented zeroes; metrics failure can coexist with a known committed release count.

Backlog counts all committed pending rows with a nonnull deadline at/before a fresh PostgreSQL clock cutoff, including locked rows. It includes cutoff, oldest deadline and overdue seconds. The count can change immediately; it is an MVCC observation, not a distributed snapshot or deduction from SKIP LOCKED. Container liveness is not functional health. External log retention, monitoring/alerts, supervision, backup/recovery and production workload/index assessment remain deployment work.

## Reproduce isolated verification

Use a **new** `olist-worker-review` (or that prefix plus a lowercase suffix) project and private env with `PGDATABASE=olist_demo`, matching explicit worker database, seeded `admin@example.com`, and no prior worker container. Follow normal build/migrate/grant/fictional seed instructions using that same target. Never reset an existing database to repeat verification.

```bash
python3 -m scripts.verify_expiry_worker --project olist-worker-review \
  --env-file .local/worker/review.env --output .local/analysis-reports/worker-new.json \
  --allow-new-fixture-time-travel
```

The tool refuses nonfresh/source-bearing/wrong-role databases and any existing worker container before writes. It appends one fictional purchase and explicitly shifts only its new reservation/purchase timestamps by one hour, retaining the 30-minute deadline. This is test preparation, not a time-travel API or a claim to have waited 30 minutes. It observes two finite cycles, two normal SIGTERM/restart sessions and the final single release, then leaves its own worker stopped and volume intact. It strips inherited Compose overrides, never logs resolved secret-bearing config and refuses existing evidence filenames. [Actual results](verification.md) and [independent review](review.md) distinguish executed evidence from these reproducible instructions.

Signal behavior follows [Python's signal model](https://docs.python.org/3.12/library/signal.html); graceful/forced container stopping follows [Compose service settings](https://docs.docker.com/reference/compose-file/services/#stop_grace_period); SQL timeout scopes are defined by [PostgreSQL](https://www.postgresql.org/docs/17/runtime-config-client.html).

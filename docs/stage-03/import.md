# Stage 3: validated Olist import

> Stage delivery record. Current setup and feature scope are in the [execution guide](../getting-started.md) and [API reference](../api.md). Commands/results below retain their original stage context.

The `import_olist` management command publishes the locked historical snapshot into the existing isolated `olist_case_study` database. It preserves operational tables and the separate legacy project's data. No command resets a database, deletes history, repairs source values, creates historical login accounts, or initializes operational inventory from purchases.

## Reproduce the import

Start with the [Docker setup](../stage-02/setup.md). Rebuild after pulling Stage 3 and apply migrations/grants with the owner service. Put the previously inspected archive at `.local/olist/brazilian-ecommerce.zip`; its SHA-256 must equal `967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784`. Obtain it from the [official source](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), following the [source inspection record](../olist/inspection.md). A changed download is refused; review a new source separately instead of changing the hash merely to bypass validation.

```bash
docker compose build app
docker compose up -d --wait db
docker compose run --rm migrate
docker compose run --rm migrate configure_database_roles
mkdir -p .local/import-reports
docker compose run --rm --user "$(id -u):$(id -g)" importer import_olist \
  --archive /data/brazilian-ecommerce.zip \
  --manifest /app/olist/source-manifest.json \
  --expected-database olist_case_study \
  --dry-run --report /reports/dry-run-new.json
docker compose run --rm --user "$(id -u):$(id -g)" importer import_olist \
  --archive /data/brazilian-ecommerce.zip \
  --manifest /app/olist/source-manifest.json \
  --expected-database olist_case_study \
  --report /reports/import-new.json
```

Use a new report filename for each execution. Repeat the second command with another filename to verify a `NOOP`. Host UID/GID execution lets the unprivileged importer write the host-owned report directory; it does not change the database role or grant owner access. Input is mounted read-only at `/data`, output at `/reports`. The importer service explicitly enables `OLIST_IMPORT_ENABLED=1`; the command also requires `olist_importer` and the exact expected database. It refuses a wrong role/database before domain writes. Do not use the Stage 2 empty-history permission probe after import.

## Validation and publication

The committed [locked manifest](../../olist/source-manifest.json) combines the previously executed source profile's file headers, byte lengths, hashes and row counts with source/version/license metadata and mapping `olist-1`. The source reports version 2 but has ambiguous version history; archive/member hashes identify the exact input. Retrieval is known to **calendar-date precision only**. Existing `DatasetSnapshot.retrieved_at` stores that date at a conventional UTC midnight; this is not an observed download instant. `retrieved_on` and this precision qualification remain explicit in the manifest/reports.

Validation reads ZIP members without extracting paths. It checks archive/member identity, unique member names, required files, UTF-8, headers, column counts, required strings/keys, postal prefixes, integers, decimal precision/ranges, source clocks, parents, and canonical duplicate identities. Item/payment sequences `1` and `01` refer to the same integer identity and cannot create two accepted records. Missing categories/attributes remain nullable; categories are the union of product keys and supplied translations. All monetary parsing uses `Decimal` and source clocks remain timezone-free, with exact raw text retained.

Reviews and geolocation are hashed/header-checked but intentionally deferred; their displayed row counts come from the locked, previously executed CSV profile. They are not counted as imported rows. Rejected or duplicate input blocks all publication. Partial import is not implemented.

A database-scoped advisory lock serializes attempts before target inspection. A second simultaneous importer fails explicitly with `IMPORT_ALREADY_RUNNING`; it does not silently skip. Publication creates dimensions, orders, every historical item/payment row, verifies all mapped content/relationships, and marks the snapshot `COMPLETE` in one transaction. Import attempts are created separately so validation/rollback failures retain their own audit record. Historical readers select only complete snapshots.

A rerun requires the same snapshot metadata, manifest and mapping, then checks counts and canonical hashes of **every persisted mapped field and relationship**, including raw dates and category translations. It refuses corrupted/incomplete data rather than declaring a successful no-op. Different input requires another isolated database. Database unique constraints remain active; conflicts are never hidden through `ignore_conflicts`.

## Report interpretation and failure behavior

Each source file reports mutually exclusive `accepted`, `duplicate_input`, and `rejected` row classifications alongside `input`; accepted rows are only proposed until publication. `imported`/`skipped` per file describe committed or verified source rows. Top-level `imported`/`skipped` count database entities, while `committed_source_rows`/`skipped_source_rows` count source rows. The full snapshot has **451,535 imported source rows** and **451,537 entities** because 71 translation rows help create 73 union-category identities.

Warnings count issues separately from distinct inconsistent rows; a valid row can have several warnings. Missing dates/categories/facts, chronology, zero payments/installments, unknown statuses/payment definitions, and payment differences are retained. `PAYMENT_ITEM_DIFFERENCE` compares separately summed payments with item prices plus freight; never multiply by installments or join the two fact tables at item/payment grain. The full report includes signed deltas for all differences above BRL 0.01, their maximum magnitude, and the aggregate signed difference across comparable orders. These are reconciliation observations, not audited revenue or manufactured adjustments.

`DRY_RUN` writes only the requested filesystem report, never domain/attempt/issue tables. It validates the current target but cannot guarantee future disk capacity or a later transaction's success. Validation/publication failures return nonzero and sanitized codes, with zero committed domain rows where publication rolled back. Diagnostic keys escape control characters. Malformed/unreadable/non-object manifests receive `INVALID_MANIFEST` JSON rather than an empty report. Existing output files are preserved.

If persisting attempt/issue metadata fails after publication, the command reports `REPORTING_FAILED`/`IMPORT_METADATA_FAILED`, preserves `data_status`, committed counts and the original failure code, and returns nonzero. It does **not** claim already committed historical data rolled back. Attempt state can remain `RUNNING`; investigate the filesystem report and database, then run the verified no-op workflow. SQL exception details/credentials are never included in those reports. Filesystem I/O failure itself cannot guarantee a writable report.

The implementation stages full normalized input in memory and checks full content on every rerun. It is sized for this archive, not an unbounded streaming ingestion system. Source owners/migration credentials can still modify history deliberately. Simulation services and the API role cannot write historical tables.

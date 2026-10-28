# API 1.4.0 logical recovery verification

## Scope and preparation

Starting point: clean `6e6a29f`, 204 executed PostgreSQL tests. The [contract](design.md) was written before implementation. This delivery adds a private trusted-source recovery drill, read-only snapshot protocol and complete-state fingerprints. No model, migration, current SQL schema, HTTP route, dependency or Olist SQL/index measurement changed. Current image/API label is 1.4.0.

New projects `olist-recovery-source` and `olist-recovery-review` use independent initialized PostgreSQL clusters, named volumes and mode-0600 env files under ignored `.local/recovery`. Source database is `olist_demo`; target default is `olist_recovery_review`. Only randomly generated new target databases are restored. The target default and earlier application/review databases are not overwritten. Source/target cluster system identifiers were checked to differ.

[Source setup](../../reports/recovery/source-setup.json) records the fictional seed and an additional keyed multi-seller order, with only that new order/reservation time-shifted to exercise actual expiry. Source contains four hashed accounts, six orders spanning the original five states plus EXPIRED, purchase snapshots and ledger/payment/shipment history. This is disclosed fictional fixture preparation, not a real elapsed-deadline claim or historical-source modification.

The existing historical benchmark was started for read-only inspection/capture. Actual query found **28 tables, 20 migrations, 99,441 historical orders and zero operational orders**. Its older schema was preserved, not silently migrated by the current capture client.

## Focused and complete PostgreSQL checks

The initial focused sequence started both new databases, migrated/configured the fictional source and ran `tests.test_recovery`: **16 tests passed in 0.315 seconds**, five commands exited 0. [Initial commands/output](../../reports/recovery/focused-first.json) are retained.

Independent review identified cleanup edge cases before publication: terminating the Compose frontend alone does not prove its snapshot container stopped, and a second frontend wait timeout must not skip cleanup. Named helpers now carry an invocation/project label; nested finalizers remove only that owned helper, including after both wait timeouts, and a nonzero client exit fails the drill. The corresponding tests execute those failure paths without touching existing containers. An additional changed-checksum test rejects the archive before restore execution.

The [final focused sequence](../../reports/recovery/focused-final.json) passed **17 tests in 0.313 seconds**, with all five commands exit 0. New tests cover simple-identifier/connection-string refusal, private exclusive directories/files, symlink/outside-output refusal, changed checksum, separate-cluster refusal, new-database/ACL failure traceability, owned-helper cleanup/nonzero exit, read-only enforcement, full auth/migration hashing, unsafe sequence/unsupported key rejection and controlled concurrent snapshot consistency.

The concurrency test holds a read-only exported snapshot, commits a new product using a distinct PostgreSQL backend, and proves the older snapshot's complete table hashes exclude that committed row while a later snapshot includes it. Coordination uses real connections and completed futures, not arbitrary delays. Sequence state is deliberately separate from the row comparison.

The complete command was:

```bash
python3 -m scripts.run_ci --output .local/recovery/ci-final
```

All nine phases/seven verification commands exited 0. **221 PostgreSQL tests passed in 13.646 seconds**; normal disposable test-database destruction is recorded. **75 role checks passed**. Strict OpenAPI validates **API 1.4.0 / 38 paths**. The unchanged committed schema/live/isolated-restore checks confirm **28 tables / 22 migrations** and exact current SQL file hash. [Summary](../../reports/recovery/local/summary.json), [checks](../../reports/recovery/local/checks.json), [roles](../../reports/recovery/local/roles.json), [OpenAPI](../../reports/recovery/local/openapi.json), [schema](../../reports/recovery/local/schema.json) and [runtime](../../reports/recovery/local/runtime.json) are actual outputs.

Actual local application runtime remains Python 3.12.15, Django 5.2.18, DRF 3.18.3, PostgreSQL 17.11, SimpleJWT 5.5.1, psycopg 3.3.6 and Ruff 0.17.2 on aarch64. The [source fingerprint reconstruction](../../reports/recovery/local-provenance.json) reproduces the checked candidate before later README evidence edits; runtime/SQL did not change after that successful run.

## Actual fictional and Olist recovery

The finalized fictional invocation was:

```bash
python3 -m scripts.recovery_drill --source-project olist-recovery-source --source-env-file .local/recovery/source.env --source-database olist_demo --target-project olist-recovery-review --target-env-file .local/recovery/target.env --private-output .local/recovery/demo-final --report reports/recovery/demo-final.json --allow-trusted-source
```

[Final fictional result](../../reports/recovery/demo-final.json): all **28 tables**, six orders and **22 applied migrations** matched across the source snapshot and restored copy; all next-ID checks passed; full DDL matched an identically reparsed source reference. The custom archive was **107,259 bytes**, with its checksum/manifest verified privately. API/importer CONNECT and API schema usage were all **false** before deliberate grant reconfiguration. Both tools actually reported PostgreSQL **17.11**; source/target locale was `en_US.utf8`, UTF-8/libc. [Initial fictional result](../../reports/recovery/demo-first.json) also passed; the final repeat added explicit tool-version/access evidence using another fresh private bundle/database pair.

The full historical invocation was:

```bash
python3 -m scripts.recovery_drill --source-project olist-benchmark --source-env-file .local/analysis/benchmark.env --source-database olist_benchmark --target-project olist-recovery-review --target-env-file .local/recovery/target.env --private-output .local/recovery/olist-full --report reports/recovery/olist-full.json --allow-trusted-source
```

[Actual Olist result](../../reports/recovery/olist-full.json): all **28 tables**, including **99,441 historical orders**, matched row counts/digests/max IDs; captured/restored history had **20 migrations**. Zero operational orders were present. Schema comparison and all 28 sequence-safety checks passed. The custom archive was **15,992,214 bytes** and its private checksum/size matched. API/importer CONNECT and API schema usage remained false. This is a faithful recovery of the benchmark's captured old version, separate from the current 22-migration application schema. No source migration, query-optimization rerun or new index gain is claimed.

All three invocations generated only new data/reference databases, recorded in their respective reports, and retained them for inspection. Source table data, auth password hashes, purchase keys/snapshots and import metadata are covered by aggregate fingerprints; individual values are not published. The drill does not claim a successful login from a hash or substitute a target-generated password for the source account's password.

## Preservation and private artifacts

[Post-drill source capture](../../reports/recovery/source-preservation.json) independently recaptured both quiescent sources: all 28 table fingerprints and migration histories remained identical. [Private artifact inspection](../../reports/recovery/private-artifact-checks.json) confirms every bundle directory 0700, dump/schema/manifest 0600, matching dump checksum/size and Git-ignore coverage. Full backups/manifests/schema captures stay under ignored `.local/recovery`; only sanitized counts/hashes/results enter Git.

[Cleanup/preservation](../../reports/recovery/local-cleanup.json) found zero remaining snapshot helpers or disposable CI resources and confirmed nine previous/new data volumes and old image tags remain. These are presence checks for unrelated environments; exact row preservation is claimed only for the two sources independently recaptured above. Source capture uses rollback and private helper cleanup; bootstrap writes occur only in the separate target to create/restrict new databases. No existing database is dropped, cleaned, terminated or reused.

See [operating/recovery guide](operations.md), [independent review](review.md) and [file inventory](changes.md). Hosted results are recorded separately after actual execution. Logical row equality, sequence next-ID safety and one local drill do not establish encrypted/offsite retention, WAL/PITR, HA or production RPO/RTO. Restore only trusted reviewed archives, provision target credentials/signing keys separately, and deliberately migrate/grant a recovery copy before enabling an application or worker.


## Actual hosted execution

Successful push [GitHub Actions run 40635471087](https://github.com/joaoltrevisan/django-orders-inventory-portfolio/actions/runs/40635471087) tested exact revision `882d36a5df67266cebe5491ce9630f89a20b9061`. [Run metadata](../../reports/recovery/github-run.json) records the event/revision, successful job/steps and UTC timestamps (created 2026-10-28T05:00:30Z). [Artifact metadata](../../reports/recovery/github-artifacts.json) identifies the uploaded archive/digest/retention.

All nine phases/seven check commands exited 0. **221 PostgreSQL tests passed in 20.950 seconds**, with normal disposable test-database destruction; **75 role checks passed**. Strict OpenAPI retained **API 1.4.0 / 38 paths**; unchanged current-schema/live/isolated restoration remained **28 tables / 22 migrations**, with exact SQL byte hash. Hosted runtime was Python 3.12.15 / PostgreSQL 17.11 on x86_64. Local/hosted durations reflect different environments, not a performance comparison.

Six actual downloaded artifacts are retained byte-for-byte: [summary](../../reports/recovery/github/summary.json), [checks](../../reports/recovery/github/checks.json), [roles](../../reports/recovery/github/roles.json), [OpenAPI](../../reports/recovery/github/openapi.json), [schema](../../reports/recovery/github/schema.json), [runtime](../../reports/recovery/github/runtime.json). Reconstructing source inputs from the exact tested Git revision matches the summary fingerprint. [Log/artifact inspection](../../reports/recovery/github-log-review.json) found none of the inspected configured source/target/benchmark/local secret values or JWT/GitHub-token/private-key patterns. Raw logs stay ignored. Deleted ephemeral hosted secrets are unavailable for a later exact-value scan, so this is not an exhaustive secret-detection claim.

The independent reviewer separately checked the hosted revision/results, exact source/schema hashes, downloaded-file identity and bounded log inspection and found no material blocker. These immutable artifacts refer to `882d36a`; the later evidence/documentation commit has its own CI checked separately. Actual full-data restore evidence above is local and private-source based; CI uses fictional test fixtures and does not download Olist data or rerun the historical backup/index experiment.

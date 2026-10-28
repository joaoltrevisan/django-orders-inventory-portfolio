# Private logical backup and recovery verification

API/image 1.4.0 adds a one-shot trusted-source recovery drill. It captures a private PostgreSQL custom archive, restores only to new databases in a separate cluster, and checks actual data/schema equality. It is not a scheduled backup service or an arbitrary-archive restoration API. No current model/migration/HTTP route or historical source query changes.

## Prepare isolated environments

Run from the repository root with host Python 3.11+ and Docker/Compose. Use two distinct existing/new configurations and project identities; never regenerate populated environment credentials. For the demonstration, create private mode-0600 source/target env files using `scripts/create_env.py`'s existing generator, deliberately selecting source database `olist_demo` and target default database `olist_recovery_review`. Use unique ports if starting HTTP, though the drill needs only PostgreSQL and one-off owner clients.

Build the current image, start each database, migrate/configure grants in the fictional source and use the existing guarded seed instructions. The target cluster needs its normal initialized roles, not application tables or accounts. Leave worker/API services disabled for this review. The target project must be `olist-recovery-review` or that prefix plus a lowercase suffix. Each real db container must use its project's own normal named data volume; cluster system identifiers must differ.

For a fresh clone only, this creates the two private configurations without printing passwords or overwriting files:

```bash
python3 - <<'PYENV'
import secrets
import tempfile
from pathlib import Path
from scripts.create_env import create_env

root = Path.cwd()
directory = root / ".local/recovery"
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as temporary:
    for kind, database, port in [
        ("source", "olist_demo", "18029"),
        ("target", "olist_recovery_review", "18030"),
    ]:
        text = (root / ".env.example").read_text()
        text = text.replace("PGDATABASE=olist_case_study", "PGDATABASE=" + database)
        text = text.replace("APP_PORT=18020", "APP_PORT=" + port)
        if kind == "source":
            text += "\nDEMO_PASSWORD=" + secrets.token_urlsafe(36) + "\n"
        template = Path(temporary) / (kind + ".env")
        template.write_text(text)
        create_env(template, directory / (kind + ".env"))
PYENV
mkdir -p .local/analysis-reports .local/import-reports
docker compose -p olist-recovery-source --env-file .local/recovery/source.env build app
docker compose -p olist-recovery-source --env-file .local/recovery/source.env up -d --wait db
docker compose -p olist-recovery-source --env-file .local/recovery/source.env run --rm migrate
docker compose -p olist-recovery-source --env-file .local/recovery/source.env \
  run --rm migrate configure_database_roles
docker compose -p olist-recovery-source --env-file .local/recovery/source.env \
  run --rm --user "$(id -u):$(id -g)" -e DEMO_SEED_ENABLED=1 migrate seed_demo \
  --expected-database olist_demo --report /reports/recovery-seed-new.json
docker compose -p olist-recovery-review --env-file .local/recovery/target.env up -d --wait db
```

Skip configuration creation/seeding when reusing an existing source; preserve its credentials and rows. The standard seed has five orders; the executed six-state evidence additionally used the explicitly recorded new keyed-expiry fixture in [source setup](../../reports/recovery/source-setup.json). Either valid source can be captured; its actual counts/digests are reported, never assumed. Choose fresh report/bundle names for each drill. Existing projects under these names must not be reset to repeat an example.

An actual fictional invocation was:

```bash
python3 -m scripts.recovery_drill \
  --source-project olist-recovery-source --source-env-file .local/recovery/source.env \
  --source-database olist_demo \
  --target-project olist-recovery-review --target-env-file .local/recovery/target.env \
  --private-output .local/recovery/demo-final --report reports/recovery/demo-final.json \
  --allow-trusted-source
```

Choose **new output names** before repeating: the tool refuses existing bundles/reports and never overwrites data. Source/target env paths and database identities are explicit; inherited Compose overrides are removed. The example's target default database is untouched. Newly generated `olist_recovery_<UUID>` data and schema-reference databases are retained, including on failure, so their identities/created flags can be inspected.

## Capture, privacy and consistency

The owner-role source client exports a read-only REPEATABLE READ snapshot and keeps it open while table fingerprints and `pg_dump --snapshot` use the same view. Raw rows are streamed into SHA-256 inside the private application process, not through public logs. All public tables, auth/M2M rows and applied migration history are included. ID ordering and UTC/ISO/float/bytea formatting are fixed. Supported sources are this project's PostgreSQL 17 UTF-8/libc public-schema normal tables with one integer `id` PK and owned identity/serial sequences; unsupported schemas/keys/views/large objects fail rather than being skipped.

Normal completion/error rolls back the source snapshot. A named/labeled one-off capture container is removed only after its invocation and project ownership are checked; finishing/terminating frontend timeouts cannot skip that cleanup. Source business rows are never updated. Keep source DDL stable during capture. Concurrent writes after the snapshot are excluded from row hashes/dump data, but sequence state has different semantics.

Each new ignored bundle has mode **0700** and contains exclusively created **0600** `database.dump`, `schema.sql` and `manifest.json`. The archive includes application password hashes and any source records, so retain it privately; mode bits do not provide encryption, offsite durability or retention. Git ignores `.local` and dump files. Reports expose counts/digests/versions/identities only; resolved config/raw errors/row data are not published.

Dump checksums detect changes relative to a trusted manifest; they do not authenticate a source or make untrusted SQL safe. PostgreSQL restore executes archive code. Use only the reviewed source, not arbitrary downloaded backups. Global PostgreSQL roles/passwords are not dumped. Custom archives may retain original owner-name metadata; `--no-owner --no-acl` is enforced at restore, not misrepresented as removing all names from archive metadata.

## What is verified

The tool restores as nonsuperuser `olist_owner` with `--single-transaction --exit-on-error --no-owner --no-acl`, after bootstrap creates fresh template0 databases and PUBLIC database/schema access is revoked. It compares every table's row count/hash/max ID and migration names with the source snapshot. A second fresh schema-only reference reparses source DDL identically, preserving CHECKs/casts/FKs/indexes/functions/triggers instead of concealing equivalent PostgreSQL coercions. Restored positive-increment, noncycling sequences must provide next IDs above maximum stored IDs and within sequence bounds; the check does not consume values.

Sequence observations are not MVCC-consistent and exact live sequence equality under concurrent writes is not claimed. Logical equality omits cluster globals, PostgreSQL internals and index statistics. A faithful backup also preserves existing anomalies; equality alone does not prove every application/business invariant or repair source history.

The actual Olist benchmark has **20 migrations**, while the current fictional/current schema has **22**. A historical drill faithfully restores its captured version. This is separate from deliberately migrating a recovery copy for the current application. [Verification](verification.md) records both actual cases; [data attribution](../../THIRD_PARTY_DATA.md) continues to apply to historical source use.

## Deliberate application access after verification

Use the report's `restored_database`, not its empty schema-reference database. Fresh restore access remains closed to API/importer; no application or worker is automatically started. To upgrade a recovery copy, explicitly select its generated database in each owner invocation:

```bash
RECOVERY_DATABASE=replace-with-the-generated-restored-database
docker compose -p olist-recovery-review --env-file .local/recovery/target.env \
  run --rm -e PGDATABASE="$RECOVERY_DATABASE" migrate migrate --check
```

For an older 20-migration copy, run normal owner migrations deliberately, then repeat the current-schema checks. That upgrade is a later state change, distinct from the original exact-restore evidence. Reapply application grants using the existing owner command:

```bash
docker compose -p olist-recovery-review --env-file .local/recovery/target.env \
  run --rm -e PGDATABASE="$RECOVERY_DATABASE" migrate configure_database_roles
docker compose -p olist-recovery-review --env-file .local/recovery/target.env \
  exec -T db psql -X -U olist_owner -d "$RECOVERY_DATABASE" \
  --set=recovered_db="$RECOVERY_DATABASE" --set=ON_ERROR_STOP=1 <<'SQL'
GRANT CONNECT ON DATABASE :"recovered_db" TO olist_api, olist_importer, olist_test;
GRANT USAGE ON SCHEMA public TO olist_api, olist_importer;
SQL
```

These commands grant access only to the explicitly selected generated copy. Confirm identities and review the restored source/code before enabling clients. Database roles use the target cluster's independently provisioned passwords; source hashes do not restore cluster credentials. Django account password hashes remain unchanged: a newly generated target `DEMO_PASSWORD` is **not** the restored users' password. Use the known private source password for a deliberate login test; do not reset hashes merely to make a demonstration pass. A new Django signing secret also means old JWTs are not automatically recovered. No post-restore authentication claim follows from row hashes alone.

## Restoring a saved trusted archive later

The drill captures/verifies in one invocation and needs its source available. For a later outage, keep the saved trusted bundle/manifest, provision a separate compatible PostgreSQL 17 cluster, verify its checksum privately, create a **new** template0 database with the recorded UTF-8/libc locale, restrict its PUBLIC access and restore as owner with the same flags. Never add `--clean`, `--create` against an existing name or delete a populated database to repeat this process. Recreate/reapply cluster credentials and grants separately, and repeat data/schema/application verification before enabling traffic.

The demonstrated locale is `en_US.utf8` for collation/ctype; use the actual saved manifest values and compatible installed locale, not a guessed default. Complete dumps/restored copies remain private. Encryption, offsite copies, retention/automation, WAL archiving/PITR, failover and measured recovery objectives require a deployment-specific plan. A local successful drill does not establish RPO/RTO guarantees.

Reference semantics: [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html), [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html) and [snapshot synchronization](https://www.postgresql.org/docs/17/functions-admin.html#FUNCTIONS-SNAPSHOT-SYNCHRONIZATION).

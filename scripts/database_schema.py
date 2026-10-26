"""Export or restore-check schema in the isolated Compose database only."""

import argparse
import difflib
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "--project-directory", str(ROOT), "exec", "-T", "db"]


def database_name():
    result = subprocess.run(
        [*COMPOSE, "printenv", "POSTGRES_DB"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def psql(database, sql, user="olist_owner"):
    result = subprocess.run(
        [*COMPOSE, "psql", "-X", "-U", user, "-d", database, "-At", "-v", "ON_ERROR_STOP=1"],
        input=sql,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def dump(database):
    return subprocess.run(
        [
            *COMPOSE,
            "pg_dump",
            "-U",
            "olist_owner",
            "-d",
            database,
            "--schema-only",
            "--no-owner",
            "--no-privileges",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def normalized(source):
    """Ignore dump headers and randomized psql safety tokens, not SQL objects."""
    return "\n".join(
        line.rstrip()
        for line in source.splitlines()
        if line.strip() and not line.startswith(("--", "\\restrict ", "\\unrestrict "))
    )


def verify(schema):
    database = database_name()
    expected = normalized(schema.read_text())
    current_dump = dump(database)
    current = normalized(current_dump)
    if expected != current:
        raise RuntimeError("Committed SQL differs from the migration-created database schema.")
    created = []
    try:
        canonical = []
        # PostgreSQL can rewrite equivalent array coercions when reparsing DDL.
        # Reparse both full schemas identically, without stripping SQL casts/checks.
        for ddl in [schema.read_text(), current_dump]:
            temporary = "olist_schema_check_" + uuid.uuid4().hex[:12]
            subprocess.run(
                [*COMPOSE, "createdb", "-U", "postgres", "--owner=olist_owner", temporary],
                check=True,
                capture_output=True,
                text=True,
            )
            created.append(temporary)
            psql(temporary, ddl)
            canonical.append(normalized(dump(temporary)))
        if canonical[0] != canonical[1]:
            difference = "\n".join(
                list(difflib.unified_diff(canonical[1].splitlines(), canonical[0].splitlines()))[
                    :50
                ]
            )
            raise RuntimeError(
                "Restored schema differs from the migration-created schema.\n" + difference
            )
        return {
            "schema_matches_migrations": True,
            "isolated_restore_matches": True,
            "normalized_schema_sha256": hashlib.sha256(expected.encode()).hexdigest(),
            "restored_canonical_sha256": hashlib.sha256(canonical[0].encode()).hexdigest(),
            "schema_file_sha256": hashlib.sha256(schema.read_bytes()).hexdigest(),
            "postgresql": psql(database, "SELECT version();"),
            "pg_dump": subprocess.run(
                [*COMPOSE, "pg_dump", "--version"], check=True, capture_output=True, text=True
            ).stdout.strip(),
            "migration_history": psql(
                database, "SELECT app || ':' || name FROM django_migrations ORDER BY app, name;"
            ).splitlines(),
            "table_count": int(
                psql(database, "SELECT count(*) FROM pg_tables WHERE schemaname='public';")
            ),
            "restore_migration_history_rows": int(
                psql(created[0], "SELECT count(*) FROM django_migrations;")
            ),
            "privileges_included": False,
            "note": (
                "Export matches the current migration-created dump. Restored full DDL "
                "matches a separately PostgreSQL-reparsed reference, including constraints, "
                "indexes, sequences, functions and triggers. Reapply grants separately. "
                "No row data is exported."
            ),
        }
    finally:
        for temporary in reversed(created):
            # Only remove the fresh UUID-named database successfully created above.
            subprocess.run(
                [*COMPOSE, "dropdb", "-U", "postgres", temporary],
                check=True,
                capture_output=True,
                text=True,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "verify"])
    parser.add_argument("--schema", type=Path, default=ROOT / "sql/schema.sql")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.action == "export":
        content = dump(database_name())
        args.schema.parent.mkdir(parents=True, exist_ok=True)
        with args.schema.open("x") as handle:
            handle.write(content)
        print("Exported schema only; existing files are never overwritten.")
    else:
        report = verify(args.schema)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open("x") as handle:
                json.dump(report, handle, indent=2)
                handle.write("\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

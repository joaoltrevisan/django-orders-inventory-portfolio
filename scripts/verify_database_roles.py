"""Check Stage 2 roles on an empty historical domain; never run after import."""

import argparse
import json
import subprocess
import uuid
from pathlib import Path

if __package__:
    from .database_schema import COMPOSE, database_name, psql
else:
    from database_schema import COMPOSE, database_name, psql


def denied(database, role, sql):
    result = subprocess.run(
        [*COMPOSE, "psql", "-X", "-U", role, "-d", database, "-At", "-v", "ON_ERROR_STOP=1"],
        input=f"BEGIN;\n{sql}\nROLLBACK;",
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 or "permission denied" not in result.stderr:
        raise RuntimeError(f"Expected an actual permission denial for role {role}.")


def verify():
    database = database_name()
    report = {"role_connections": {}, "checks_passed": 0}
    for role in ["olist_api", "olist_importer", "olist_test", "olist_owner"]:
        flags = json.loads(
            psql(
                database,
                """SELECT json_build_object(
            'user', current_user, 'superuser', rolsuper, 'create_role', rolcreaterole,
            'create_database', rolcreatedb,
            'owns_database', current_user = pg_get_userbyid(d.datdba),
            'owner_membership', pg_has_role(current_user, 'olist_owner', 'MEMBER'),
            'test_membership', pg_has_role(current_user, 'olist_test', 'MEMBER'))
            FROM pg_roles r CROSS JOIN pg_database d
            WHERE r.rolname=current_user AND d.datname=current_database();""",
                user=role,
            )
        )
        assert flags["user"] == role
        assert not flags["superuser"] and not flags["create_role"]
        assert flags["create_database"] == (role == "olist_test")
        assert flags["owns_database"] == (role == "olist_owner")
        if role in ["olist_api", "olist_importer"]:
            assert not flags["owner_membership"] and not flags["test_membership"]
        report["role_connections"][role] = flags
        report["checks_passed"] += 1

    history_tables = psql(
        database,
        "SELECT tablename FROM pg_tables WHERE schemaname='public' "
        "AND tablename LIKE 'olist_%' ORDER BY tablename;",
    ).splitlines()
    # This safety gate must work even when Python assertions are disabled.
    for table in history_tables:
        if psql(database, f"SELECT count(*) FROM {table};") != "0":
            raise RuntimeError(
                "Role probes require an empty historical domain. No probes executed."
            )
    for table in history_tables:
        assert psql(database, f"SELECT count(*) FROM {table};", user="olist_api") == "0"
        for operation in ["INSERT", "UPDATE", "DELETE", "TRUNCATE"]:
            allowed = psql(
                database,
                f"SELECT has_table_privilege(current_user, '{table}', '{operation}');",
                user="olist_api",
            )
            assert allowed == "f", (table, operation)
            report["checks_passed"] += 1
    for table in ["olist_order", "olist_import_run"]:
        for sql in [
            f"INSERT INTO {table} (id) VALUES (-1);",
            f"UPDATE {table} SET id=id WHERE false;",
            f"DELETE FROM {table} WHERE false;",
            f"TRUNCATE {table};",
        ]:
            denied(database, "olist_api", sql)
            report["checks_passed"] += 1
    for role in ["olist_api", "olist_importer"]:
        denied(database, role, "CREATE TABLE forbidden_role_probe (id integer);")
        denied(database, role, "SET ROLE olist_owner;")
        denied(database, role, "SET ROLE olist_test;")
        report["checks_passed"] += 3
    for role, target in [
        ("olist_api", "olist_importer"),
        ("olist_importer", "olist_api"),
        ("olist_test", "olist_owner"),
        ("olist_test", "olist_api"),
        ("olist_test", "olist_importer"),
    ]:
        denied(database, role, f"SET ROLE {target};")
        report["checks_passed"] += 1
    for role in ["olist_api", "olist_importer"]:
        denied(database, role, "UPDATE django_migrations SET id=id WHERE false;")
        report["checks_passed"] += 1
    denied(
        database,
        "olist_importer",
        "UPDATE olist_order SET source_status=source_status WHERE false;",
    )
    denied(database, "olist_importer", "DELETE FROM olist_order WHERE false;")
    denied(database, "olist_importer", "TRUNCATE olist_order;")
    denied(
        database,
        "olist_importer",
        "UPDATE olist_dataset_snapshot SET archive_sha256=archive_sha256 WHERE false;",
    )
    psql(
        database,
        "UPDATE olist_dataset_snapshot SET publication_status=publication_status WHERE false;",
        user="olist_importer",
    )
    psql(database, "UPDATE olist_import_run SET counts=counts WHERE false;", user="olist_importer")
    psql(database, "UPDATE catalog_offer SET is_active=is_active WHERE false;", user="olist_api")
    report["checks_passed"] += 7
    future = "stage2_future_" + uuid.uuid4().hex[:12]
    created = False
    try:
        psql(database, f"CREATE TABLE {future} (id integer);")
        created = True
        psql(database, f"SELECT count(*) FROM {future};", user="olist_api")
        denied(database, "olist_api", f"UPDATE {future} SET id=id WHERE false;")
        denied(database, "olist_importer", f"SELECT count(*) FROM {future};")
        report["checks_passed"] += 3
    finally:
        if created:
            psql(database, f"DROP TABLE {future};")
    report["historical_tables_checked"] = history_tables
    report["historical_domain_rows"] = 0
    report["note"] = (
        "Role authorization checked with separate psql sessions inside the isolated container. "
        "Application TCP password authentication is checked by health startup. "
        "No source data imported."
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = verify()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))

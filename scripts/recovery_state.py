"""Read-only snapshot fingerprints; raw rows stay inside the application process."""

import hashlib
import uuid
from contextlib import contextmanager

from django.db import transaction
from psycopg import sql


@contextmanager
def read_snapshot(database):
    if database.in_atomic_block:
        raise RuntimeError("Recovery capture requires its own snapshot transaction.")
    with transaction.atomic(using=database.alias):
        with database.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute(
                "SET LOCAL TimeZone='UTC'; SET LOCAL DateStyle='ISO, YMD'; "
                "SET LOCAL extra_float_digits=3; SET LOCAL bytea_output='hex'; "
                "SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='120s'; "
                "SET LOCAL idle_in_transaction_session_timeout='300s'"
            )
            cursor.execute("SELECT pg_export_snapshot()")
            try:
                yield cursor.fetchone()[0]
            finally:
                transaction.set_rollback(True, using=database.alias)


def capture_state(database):
    with database.cursor() as cursor:
        cursor.execute(
            "SELECT current_setting('transaction_isolation'),"
            "current_setting('transaction_read_only')"
        )
        if cursor.fetchone() != ("repeatable read", "on"):
            raise RuntimeError("Recovery state requires a read-only repeatable snapshot.")
        cursor.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname NOT IN "
            "('public','pg_catalog','information_schema') AND nspname NOT LIKE 'pg_toast%' "
            "AND nspname NOT LIKE 'pg_temp%'"
        )
        if cursor.fetchall():
            raise RuntimeError("Recovery supports the project's public schema only.")
        cursor.execute("SELECT count(*) FROM pg_largeobject_metadata")
        if cursor.fetchone()[0]:
            raise RuntimeError("Large objects are outside the reviewed recovery scope.")
        cursor.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind IN ('v','m','f','p')"
        )
        if cursor.fetchone()[0]:
            raise RuntimeError("Unsupported public relation in recovery source.")
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
        tables = [row[0] for row in cursor.fetchall()]
    result = {"tables": {}, "sequences": {}, "migration_history": []}
    for table in tables:
        identifier = sql.Identifier("public", table)
        reference = identifier.as_string(database.connection)
        with database.cursor() as cursor:
            cursor.execute(
                "SELECT array_agg(a.attname ORDER BY k.ordinality) "
                "FROM pg_constraint c CROSS JOIN LATERAL unnest(c.conkey) "
                "WITH ORDINALITY k(attnum,ordinality) JOIN pg_attribute a "
                "ON a.attrelid=c.conrelid AND a.attnum=k.attnum "
                "WHERE c.contype='p' AND c.conrelid=%s::regclass",
                [reference],
            )
            if cursor.fetchone()[0] != ["id"]:
                raise RuntimeError("Recovery requires a single id primary key on each table.")
            cursor.execute(
                "SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
                "WHERE attrelid=%s::regclass AND attname='id'",
                [reference],
            )
            if cursor.fetchone()[0] not in {"bigint", "integer", "smallint"}:
                raise RuntimeError("Recovery requires integer id keys.")
            cursor.execute("SELECT pg_get_serial_sequence(%s,'id')", [reference])
            sequence = cursor.fetchone()[0]
        digest, count, maximum = hashlib.sha256(), 0, None
        with database.connection.cursor(name="recovery_" + uuid.uuid4().hex) as rows:
            rows.execute(
                sql.SQL("SELECT id,to_jsonb(t)::text FROM {} t ORDER BY id").format(identifier)
            )
            for key, encoded in rows:
                digest.update(encoded.encode("utf-8") + b"\n")
                count += 1
                maximum = key
        result["tables"][table] = {"rows": count, "sha256": digest.hexdigest(), "max_id": maximum}
        if sequence is None:
            raise RuntimeError("Recovery requires owned identity/serial sequences.")
        with database.cursor() as cursor:
            cursor.execute(
                "SELECT n.nspname,c.relname,s.seqincrement,s.seqmax,s.seqcycle "
                "FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE s.seqrelid=%s::regclass",
                [sequence],
            )
            namespace, name, increment, bound, cycle = cursor.fetchone()
            cursor.execute(
                sql.SQL("SELECT last_value,is_called FROM {}").format(
                    sql.Identifier(namespace, name)
                )
            )
            last, called = cursor.fetchone()
        next_value = last + increment if called else last
        safe = (
            increment > 0
            and not cycle
            and next_value <= bound
            and (maximum is None or next_value > maximum)
        )
        result["sequences"][table] = {"next_value": next_value, "safe": safe}
        if not safe:
            raise RuntimeError("Sequence next-ID safety check failed.")
    with database.cursor() as cursor:
        cursor.execute("SELECT app,name FROM django_migrations ORDER BY app,name")
        result["migration_history"] = [app + ":" + name for app, name in cursor.fetchall()]
    return result

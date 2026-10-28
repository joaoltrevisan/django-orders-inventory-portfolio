"""Recovery integrity, consistent snapshots and non-destructive target guards."""

import hashlib
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import DatabaseError, close_old_connections, connection, connections
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from psycopg import sql

from catalog.models import Product
from scripts import recovery_drill as recovery
from scripts.recovery_state import capture_state, read_snapshot

from .operational_fixture import operational_fixture


class RecoveryGuardTests(SimpleTestCase):
    def test_database_names_cannot_be_conninfo_paths_or_options(self):
        for value in [
            "host=external",
            "postgres://example.com/db",
            "-d",
            "a/b",
            "A",
            "a;DROP DATABASE x",
            "x" * 64,
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                recovery.identifier(value)
        self.assertEqual(recovery.identifier("olist_recovery_123abc"), "olist_recovery_123abc")

    def test_private_bundle_requires_new_ignored_directory_and_refuses_symlinks(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(recovery, "ROOT", Path(temporary)),
        ):
            root = Path(temporary)
            path = root / ".local/recovery/new"
            self.assertEqual(recovery.private_bundle(path), path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(FileExistsError):
                recovery.private_bundle(path)
            with self.assertRaises(ValueError):
                recovery.private_bundle(root / "outside")
            linked = root / ".local/recovery/link"
            linked.symlink_to(path, target_is_directory=True)
            with self.assertRaises(ValueError):
                recovery.private_bundle(linked / "child")

    def test_private_files_are_exclusive_0600_and_corruption_changes_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "private.dump"
            with recovery.private_file(path) as output:
                output.write(b"private data")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            original = recovery.file_hash(path)
            with self.assertRaises(FileExistsError):
                recovery.private_file(path)
            path.write_bytes(b"corrupted data")
            self.assertNotEqual(recovery.file_hash(path), original)

    def test_endpoint_strips_compose_overrides_and_uses_private_file_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = Path(temporary) / "review.env"
            env.write_text("PGDATABASE=olist_demo\nAPP_DB_PASSWORD=private-fixture-value\n")
            env.chmod(0o600)
            with patch.dict(
                "os.environ", {"COMPOSE_FILE": "other.yaml", "APP_DB_PASSWORD": "wrong"}
            ):
                endpoint = recovery.Endpoint("olist-review", env)
            self.assertNotIn("COMPOSE_FILE", endpoint.environment)
            self.assertEqual(endpoint.environment["APP_DB_PASSWORD"], "private-fixture-value")
            self.assertIn(str(env), endpoint.compose)
            self.assertNotIn("private-fixture-value", " ".join(endpoint.compose))
            env.chmod(0o644)
            with self.assertRaises(ValueError):
                recovery.Endpoint("olist-review", env)

    def test_database_creation_failure_never_reuses_or_cleans_an_existing_database(self):
        endpoint = object.__new__(recovery.Endpoint)
        endpoint.run = MagicMock(side_effect=RuntimeError("createdb refused"))
        endpoint.psql = MagicMock()
        report = {}
        with self.assertRaises(RuntimeError):
            endpoint.create_database({"collation": "C", "ctype": "C"}, report, "data")
        self.assertEqual(len(report["new_databases"]), 1)
        self.assertFalse(next(iter(report["new_databases"].values()))["created"])
        endpoint.psql.assert_not_called()
        command = endpoint.run.call_args.args[0]
        self.assertIn("--template=template0", command)
        self.assertNotIn("--clean", command)
        self.assertNotIn("--if-exists", command)

    def test_acl_failure_keeps_created_database_identity_for_inspection(self):
        endpoint = object.__new__(recovery.Endpoint)
        endpoint.run = MagicMock()
        endpoint.psql = MagicMock(side_effect=RuntimeError("ACL failed"))
        report = {}
        with self.assertRaises(RuntimeError):
            endpoint.create_database({"collation": "C", "ctype": "C"}, report, "data")
        self.assertTrue(next(iter(report["new_databases"].values()))["created"])

    def test_shared_clusters_are_refused_before_a_snapshot_or_restore(self):
        source, target = MagicMock(project="source"), MagicMock(project="target")
        source.inspect.return_value = ("source-container", "source-volume")
        target.inspect.return_value = ("target-container", "target-volume")
        source.psql.return_value = target.psql.return_value = b"same-system-identifier"
        with patch.object(recovery, "Snapshot") as snapshot, self.assertRaises(RuntimeError):
            recovery.drill(source, target, "olist_demo", Path("unused"), {})
        snapshot.assert_not_called()
        target.create_database.assert_not_called()

    def snapshot_stub(self, returncode=0):
        snapshot = recovery.Snapshot(
            SimpleNamespace(environment={}, project="review"), "olist_demo"
        )
        snapshot.process = MagicMock(returncode=returncode)
        snapshot.process.poll.return_value = returncode
        snapshot.process.stdin.closed = False
        snapshot.errors = MagicMock()
        snapshot.name, snapshot.invocation = "allocated-snapshot", "owned-token"
        return snapshot

    def test_snapshot_cleanup_refuses_foreign_container(self):
        snapshot = self.snapshot_stub()
        listing = subprocess.CompletedProcess([], 0, stdout=b"allocated-snapshot\n")
        foreign = subprocess.CompletedProcess(
            [],
            0,
            stdout=json.dumps(
                [{"Config": {"Labels": {"olist.recovery.invocation": "foreign"}}}]
            ).encode(),
        )
        with (
            patch.object(recovery.subprocess, "run", side_effect=[listing, foreign]) as run,
            self.assertRaises(RuntimeError),
        ):
            snapshot.__exit__(None, None, None)
        self.assertFalse(any("rm" in call.args[0] for call in run.call_args_list))

    def test_nonzero_snapshot_exit_is_not_silently_successful(self):
        snapshot = self.snapshot_stub(returncode=1)
        absent = subprocess.CompletedProcess([], 0, stdout=b"")
        with (
            patch.object(recovery.subprocess, "run", return_value=absent),
            self.assertRaises(RuntimeError),
        ):
            snapshot.__exit__(None, None, None)

    def test_only_owned_snapshot_helper_can_be_removed(self):
        snapshot = self.snapshot_stub()
        listing = subprocess.CompletedProcess([], 0, stdout=b"allocated-snapshot\n")
        owned = subprocess.CompletedProcess(
            [],
            0,
            stdout=json.dumps(
                [
                    {
                        "Config": {
                            "Labels": {
                                "olist.recovery.invocation": "owned-token",
                                "com.docker.compose.project": "review",
                            }
                        }
                    }
                ]
            ).encode(),
        )
        with patch.object(
            recovery.subprocess,
            "run",
            side_effect=[listing, owned, subprocess.CompletedProcess([], 0)],
        ) as run:
            snapshot.__exit__(None, None, None)
        self.assertEqual(run.call_args.args[0], ["docker", "rm", "--force", "allocated-snapshot"])

    def test_both_frontend_wait_timeouts_still_remove_only_owned_helper(self):
        snapshot = self.snapshot_stub(returncode=-9)
        snapshot.process.poll.return_value = None
        snapshot.process.wait.side_effect = [
            subprocess.TimeoutExpired("finish", 15),
            subprocess.TimeoutExpired("terminate", 10),
            -9,
        ]
        listing = subprocess.CompletedProcess([], 0, stdout=b"allocated-snapshot\n")
        owned = subprocess.CompletedProcess(
            [],
            0,
            stdout=json.dumps(
                [
                    {
                        "Config": {
                            "Labels": {
                                "olist.recovery.invocation": "owned-token",
                                "com.docker.compose.project": "review",
                            }
                        }
                    }
                ]
            ).encode(),
        )
        with (
            patch.object(
                recovery.subprocess,
                "run",
                side_effect=[listing, owned, subprocess.CompletedProcess([], 0)],
            ) as run,
            self.assertRaises(RuntimeError),
        ):
            snapshot.__exit__(None, None, None)
        snapshot.process.terminate.assert_called_once()
        snapshot.process.kill.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["docker", "rm", "--force", "allocated-snapshot"])
        snapshot.errors.close.assert_called_once()

    def test_changed_dump_checksum_refuses_restore_execution(self):
        source, target = MagicMock(project="source"), MagicMock(project="target")
        source.inspect.return_value = ("source-container", "source-volume")
        target.inspect.return_value = ("target-container", "target-volume")
        source.psql.return_value, target.psql.return_value = b"1", b"2"
        source.run.return_value = target.run.return_value = b"PostgreSQL 17.11"
        source.dump_schema.return_value = b"CREATE TABLE fixture (id bigint);"
        target.create_database.side_effect = ["olist_recovery_a", "olist_recovery_b"]
        context = MagicMock()
        context.metadata = {"snapshot": "00000001-00000001-1"}
        context.capture.return_value = {"tables": {}, "migration_history": []}
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(recovery, "Snapshot") as snapshot,
        ):
            snapshot.return_value.__enter__.return_value = context
            with (
                patch.object(recovery, "file_hash", side_effect=["original", "changed"]),
                patch.object(recovery.subprocess, "run") as restore,
                self.assertRaisesRegex(RuntimeError, "checksum"),
            ):
                recovery.drill(source, target, "olist_demo", Path(temporary), {})
            restore.assert_not_called()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RecoveryPostgreSQLTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        operational_fixture(self)

    def test_capture_requires_an_explicit_read_only_snapshot(self):
        with self.assertRaises(RuntimeError):
            capture_state(connection)
        with read_snapshot(connection):
            with self.assertRaises(DatabaseError):
                Product.objects.create(sku="FORBIDDEN", name="Read-only mutation")
        self.assertFalse(Product.objects.filter(sku="FORBIDDEN").exists())

    def test_all_tables_password_rows_and_migrations_are_fingerprinted_deterministically(self):
        with read_snapshot(connection):
            first, second = capture_state(connection), capture_state(connection)
        self.assertEqual(first, second)
        self.assertEqual(len(first["tables"]), 28)
        self.assertEqual(first["tables"]["accounts_user"]["rows"], 3)
        self.assertEqual(first["tables"]["django_migrations"]["rows"], 22)
        self.assertEqual(len(first["migration_history"]), 22)
        self.assertTrue(all(seq["safe"] for seq in first["sequences"].values()))
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_jsonb(t)::text FROM accounts_user t ORDER BY id")
            expected = hashlib.sha256(
                b"".join(row[0].encode() + b"\n" for row in cursor.fetchall())
            ).hexdigest()
        self.assertEqual(first["tables"]["accounts_user"]["sha256"], expected)
        self.assertNotIn(self.buyer.password, json.dumps(first))

    def test_later_commit_is_excluded_from_exported_snapshot_using_separate_connections(self):
        with read_snapshot(connection):
            before = capture_state(connection)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                holder = cursor.fetchone()[0]

            def commit_later():
                close_old_connections()
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        writer = cursor.fetchone()[0]
                    Product.objects.create(sku="LATER-COMMIT", name="Post-snapshot product")
                    return writer
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=1) as pool:
                writer = pool.submit(commit_later).result(timeout=5)
            self.assertNotEqual(holder, writer)
            after = capture_state(connection)
            self.assertEqual(before["tables"], after["tables"])
            self.assertEqual(before["migration_history"], after["migration_history"])
        self.assertTrue(Product.objects.filter(sku="LATER-COMMIT").exists())
        with read_snapshot(connection):
            latest = capture_state(connection)
        self.assertEqual(
            latest["tables"]["catalog_product"]["rows"],
            before["tables"]["catalog_product"]["rows"] + 1,
        )
        print(
            "PostgreSQL recovery snapshot: "
            + json.dumps(
                {
                    "snapshot_backend_pid": holder,
                    "writer_backend_pid": writer,
                    "later_committed_row_excluded": True,
                }
            ),
            flush=True,
        )

    def test_unsafe_next_id_is_rejected_without_consuming_sequence_values(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_get_serial_sequence('catalog_product','id')")
            sequence = cursor.fetchone()[0]
            cursor.execute(
                sql.SQL("SELECT last_value,is_called FROM {}").format(
                    sql.Identifier(*sequence.split("."))
                )
            )
            last, called = cursor.fetchone()
            cursor.execute("SELECT setval(%s::regclass,1,false)", [sequence])
        try:
            with read_snapshot(connection), self.assertRaisesRegex(RuntimeError, "Sequence"):
                capture_state(connection)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT setval(%s::regclass,%s,%s)", [sequence, last, called])

    def test_composite_or_non_id_primary_keys_are_not_silently_skipped(self):
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE recovery_composite(a integer,b integer,PRIMARY KEY(a,b))")
        try:
            with read_snapshot(connection), self.assertRaisesRegex(RuntimeError, "single id"):
                capture_state(connection)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE recovery_composite")

import json
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from accounts.models import User
from olist.importer import ImportFailure, import_archive, validate_archive
from olist.models import (
    Category,
    DatasetSnapshot,
    HistoricalCustomer,
    HistoricalOrder,
    HistoricalOrderItem,
    HistoricalPaymentRecord,
    HistoricalProduct,
    HistoricalSeller,
    ImportIssue,
    ImportRun,
)

from .olist_fixture import key, write_fixture


class ImporterTests(TransactionTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.archive, self.manifest = write_fixture(self.directory.name)
        self.database = connection.settings_dict["NAME"]

    def execute(self, **kwargs):
        return import_archive(
            archive=kwargs.pop("archive", self.archive),
            manifest=kwargs.pop("manifest", self.manifest),
            expected_database=self.database,
            **kwargs,
        )

    def test_complete_import_preserves_grains_money_clock_and_anomalies(self):
        report = self.execute()
        self.assertEqual(report["status"], "SUCCEEDED")
        self.assertEqual(report["rejected"], 0)
        self.assertEqual(report["duplicate_input"], 0)
        self.assertEqual(
            HistoricalCustomer.objects.values("customer_unique_id").distinct().count(), 1
        )
        self.assertEqual(HistoricalOrderItem.objects.count(), 3)
        self.assertEqual(HistoricalSeller.objects.count(), 2)
        self.assertEqual(HistoricalPaymentRecord.objects.count(), 3)
        self.assertEqual(Category.objects.count(), 2)
        self.assertIsNone(Category.objects.get(source_name="untranslated_fixture").english_name)
        self.assertEqual(
            HistoricalCustomer.objects.get(source_customer_id=key(1)).zip_code_prefix, "00123"
        )
        order = HistoricalOrder.objects.get(source_order_id=key(6))
        self.assertEqual(
            order.purchased_at_source.strftime("%Y-%m-%d %H:%M:%S"), order.purchased_at_raw
        )
        self.assertIsNone(order.purchased_at_source.tzinfo)
        self.assertIsNone(order.approved_at_source)
        self.assertEqual(report["reconciliation"]["exact_matches"], 1)
        self.assertIn("CANCELED_WITH_DELIVERY", report["issue_counts"])
        self.assertIn("ZERO_PAYMENT_VALUE", report["issue_counts"])
        self.assertGreater(report["inconsistent_rows"], 0)
        self.assertGreater(ImportIssue.objects.count(), 0)
        self.assertEqual(DatasetSnapshot.objects.get().publication_status, "COMPLETE")
        self.assertEqual(ImportRun.objects.get().status, "SUCCEEDED")
        self.assertEqual(User.objects.count(), 0)

    def test_verified_rerun_is_noop_and_corruption_or_different_manifest_is_refused(self):
        first = self.execute()
        second = self.execute()
        self.assertEqual(second["status"], "NOOP")
        self.assertEqual(second["skipped"], first["imported"])
        self.assertEqual(HistoricalOrder.objects.count(), 2)
        self.assertEqual(ImportRun.objects.count(), 2)
        HistoricalOrder.objects.filter(source_order_id=key(6)).update(source_status="changed")
        with self.assertRaises(ImportFailure) as error:
            self.execute()
        self.assertIn("PERSISTED_CONTENT_MISMATCH", error.exception.code)
        other = {**self.manifest, "reported_version": "different"}
        with self.assertRaises(ImportFailure) as error:
            self.execute(manifest=other)
        self.assertEqual(error.exception.code, "SNAPSHOT_CONFLICT")

    def test_dry_run_never_writes_domain_attempt_or_issue_rows(self):
        report = self.execute(dry_run=True)
        self.assertEqual(report["status"], "DRY_RUN")
        self.assertGreater(report["proposed_entities"]["items"], 0)
        for model in [DatasetSnapshot, HistoricalOrder, ImportRun, ImportIssue]:
            self.assertEqual(model.objects.count(), 0)

    def test_structural_errors_and_duplicate_inputs_block_entire_publication(self):
        mutations = [
            lambda rows: rows["items"].append(list(rows["items"][0])),
            lambda rows: rows["items"][0].__setitem__(2, key(999)),
            lambda rows: rows["items"][0].__setitem__(5, "NaN"),
            lambda rows: rows["items"][0].__setitem__(1, "1.5"),
            lambda rows: rows["orders"][0].__setitem__(3, "2017-03-01T00:00:00Z"),
            lambda rows: rows["customers"][0].__setitem__(2, "123"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                archive, manifest = write_fixture(
                    self.directory.name, mutate=mutate, label=str(index)
                )
                with self.assertRaises(ImportFailure) as error:
                    self.execute(archive=archive, manifest=manifest)
                self.assertEqual(error.exception.report["imported"], 0)
                self.assertEqual(error.exception.code, "SOURCE_VALIDATION_FAILED")
                self.assertFalse(HistoricalOrder.objects.exists())
                self.assertFalse(DatasetSnapshot.objects.exists())
        self.assertEqual(ImportRun.objects.filter(status="FAILED").count(), len(mutations))

    def test_hash_guard_and_expected_database_guard(self):
        manifest = {**self.manifest, "archive_sha256": "0" * 64}
        with self.assertRaises(ImportFailure) as error:
            self.execute(manifest=manifest)
        self.assertEqual(error.exception.code, "ARCHIVE_HASH_MISMATCH")
        with self.assertRaises(ImportFailure) as error:
            import_archive(
                archive=self.archive, manifest=self.manifest, expected_database="unrelated"
            )
        self.assertEqual(error.exception.code, "TARGET_DATABASE_MISMATCH")
        self.assertEqual(ImportRun.objects.count(), 1)

    def test_manifest_source_url_must_be_valid_text_before_any_publication(self):
        for value in [{}, [], "invalid url"]:
            with self.assertRaises(ImportFailure) as error:
                self.execute(manifest={**self.manifest, "source_url": value})
            self.assertEqual(error.exception.code, "INVALID_SOURCE_URL")
        self.assertFalse(DatasetSnapshot.objects.exists())

    def test_command_manifest_failures_always_write_sanitized_json(self):
        for number, content in enumerate(["invalid json", "[]", "null", None]):
            manifest_path = Path(self.directory.name) / f"bad-{number}.json"
            report_path = Path(self.directory.name) / f"report-{number}.json"
            if content is not None:
                manifest_path.write_text(content)
            with (
                patch.dict(os.environ, {"OLIST_IMPORT_ENABLED": "1"}),
                patch("olist.management.commands.import_olist.connection") as database,
            ):
                database.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                    "olist_importer",
                    "fixture",
                )
                with self.assertRaises(CommandError):
                    call_command(
                        "import_olist",
                        archive=self.archive,
                        manifest=manifest_path,
                        expected_database="fixture",
                        report=report_path,
                    )
            report = json.loads(report_path.read_text())
            self.assertEqual(report["failure_code"], "INVALID_MANIFEST")
            self.assertEqual(report["imported"], 0)
        self.assertFalse(ImportRun.objects.exists())

    def test_metadata_failure_preserves_committed_publication_and_structured_report(self):
        with patch(
            "olist.importer.ImportIssue.objects.bulk_create",
            side_effect=RuntimeError("private detail"),
        ):
            with self.assertRaises(ImportFailure) as error:
                self.execute()
        report = error.exception.report
        self.assertEqual(report["failure_code"], "IMPORT_METADATA_FAILED")
        self.assertEqual(report["data_status"], "SUCCEEDED")
        self.assertGreater(report["imported"], 0)
        self.assertNotIn("private detail", str(report))
        self.assertFalse(report["metadata_persisted"])
        self.assertEqual(DatasetSnapshot.objects.get().publication_status, "COMPLETE")
        self.assertEqual(ImportRun.objects.get().status, "RUNNING")
        self.assertEqual(self.execute()["status"], "NOOP")

    def test_metadata_failure_before_publication_preserves_original_validation_failure(self):
        archive, manifest = write_fixture(
            self.directory.name, mutate=lambda rows: rows["items"][0].__setitem__(5, "NaN")
        )
        with patch(
            "olist.importer.ImportIssue.objects.bulk_create",
            side_effect=RuntimeError("private detail"),
        ):
            with self.assertRaises(ImportFailure) as error:
                self.execute(archive=archive, manifest=manifest)
        self.assertEqual(error.exception.report["primary_failure_code"], "SOURCE_VALIDATION_FAILED")
        self.assertEqual(error.exception.report["data_status"], "FAILED")
        self.assertEqual(error.exception.report["imported"], 0)
        self.assertFalse(DatasetSnapshot.objects.exists())

    def test_duplicate_sequences_are_compared_as_persisted_integers(self):
        def duplicate(rows):
            repeated = list(rows["items"][0])
            repeated[1] = "01"
            rows["items"].append(repeated)

        archive, manifest = write_fixture(self.directory.name, mutate=duplicate)
        with self.assertRaises(ImportFailure) as error:
            self.execute(archive=archive, manifest=manifest)
        self.assertEqual(error.exception.report["duplicate_input"], 1)
        self.assertEqual(error.exception.code, "SOURCE_VALIDATION_FAILED")
        self.assertFalse(HistoricalOrder.objects.exists())

    def test_database_failure_rolls_back_all_history_and_keeps_failed_attempt(self):
        from olist.importer import publish

        def fail_after_inserts(entities, snapshot):
            publish(entities, snapshot)
            raise RuntimeError("forced failure after inserts")

        with patch("olist.importer.publish", side_effect=fail_after_inserts):
            with self.assertRaises(ImportFailure):
                self.execute()
        for model in [
            DatasetSnapshot,
            HistoricalCustomer,
            HistoricalProduct,
            HistoricalSeller,
            HistoricalOrder,
            HistoricalOrderItem,
            HistoricalPaymentRecord,
            Category,
        ]:
            self.assertEqual(model.objects.count(), 0)
        self.assertEqual(ImportRun.objects.get().status, "FAILED")
        self.assertIsNone(ImportRun.objects.get().snapshot_id)
        self.assertEqual(self.execute()["status"], "SUCCEEDED")

    def test_concurrent_import_refused_on_separate_connection_with_controlled_lock(self):
        acquired, release = threading.Event(), threading.Event()
        errors = []
        backend_ids = []
        outcomes = []

        def controlled_validation(*args):
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_ids.append(cursor.fetchone()[0])
            acquired.set()
            if not release.wait(10):
                raise TimeoutError("Controlled import validation was not released.")
            return validate_archive(*args)

        def holder():
            close_old_connections()
            try:
                outcomes.append(self.execute())
            except Exception as error:
                errors.append(error)
                acquired.set()
            finally:
                connections["default"].close()

        with patch("olist.importer.validate_archive", side_effect=controlled_validation):
            thread = threading.Thread(target=holder)
            thread.start()
            try:
                self.assertTrue(acquired.wait(10))
                self.assertFalse(errors, errors)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    self.assertNotEqual(cursor.fetchone()[0], backend_ids[0])
                    cursor.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_locks "
                        "WHERE locktype='advisory' AND pid=%s AND granted)",
                        [backend_ids[0]],
                    )
                    self.assertTrue(cursor.fetchone()[0])
                with self.assertRaises(ImportFailure) as error:
                    self.execute()
                self.assertEqual(error.exception.code, "IMPORT_ALREADY_RUNNING")
                self.assertEqual(ImportRun.objects.count(), 1)
                self.assertFalse(DatasetSnapshot.objects.exists())
            finally:
                release.set()
                thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors, errors)
        self.assertEqual(outcomes[0]["status"], "SUCCEEDED")
        self.assertEqual(self.execute()["status"], "NOOP")

    def test_snapshot_provenance_corruption_is_refused(self):
        self.execute()
        DatasetSnapshot.objects.update(license_identifier="incorrect")
        with self.assertRaises(ImportFailure) as error:
            self.execute()
        self.assertEqual(error.exception.code, "SNAPSHOT_CONFLICT")

    def test_invalid_diagnostic_key_does_not_prevent_failure_reporting(self):
        archive, manifest = write_fixture(
            self.directory.name, mutate=lambda rows: rows["customers"][0].__setitem__(0, "\x00")
        )
        with self.assertRaises(ImportFailure) as error:
            self.execute(archive=archive, manifest=manifest)
        self.assertEqual(error.exception.code, "SOURCE_VALIDATION_FAILED")
        self.assertTrue(error.exception.report["metadata_persisted"])
        self.assertNotIn("\x00", str(error.exception.report))
        self.assertEqual(ImportRun.objects.get().status, "FAILED")

    def test_signed_reconciliation_delta_is_reported_without_changing_payments(self):
        archive, manifest = write_fixture(
            self.directory.name, mutate=lambda rows: rows["payments"][1].__setitem__(4, "9.00")
        )
        report = self.execute(archive=archive, manifest=manifest)
        self.assertEqual(report["reconciliation"]["maximum_absolute_difference"], "1.00")
        self.assertEqual(
            report["reconciliation"]["differences_above_001"][0]["payment_minus_items_and_freight"],
            "1.00",
        )
        self.assertEqual(
            str(HistoricalPaymentRecord.objects.get(payment_sequential=2).payment_value), "9.00"
        )

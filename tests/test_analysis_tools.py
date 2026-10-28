import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Sum
from django.test import TestCase, TransactionTestCase

from accounts.models import Customer, User
from inventory.models import Stock, StockMovement
from olist.benchmark import INDEX_NAME, query_rows, run_experiment, validate_target
from olist.importer import import_archive
from olist.models import DatasetSnapshot
from orders.demo import seed_demo
from orders.models import Order

from .olist_fixture import write_fixture


class DemoSeedTests(TestCase):
    def seed(self):
        return seed_demo(
            expected_database=connection.settings_dict["NAME"],
            password="Fictional-seed-password-4729!",
        )

    def test_seed_is_fictional_hashed_auditable_and_refuses_repeat_without_reset(self):
        report = self.seed()
        self.assertEqual(report["data_origin"], "SIMULATED_API")
        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(Customer.objects.count(), 3)
        # The stable seed retains five states; expiry uses a separate scoped fixture.
        self.assertEqual(
            set(Order.objects.values_list("status", flat=True)),
            set(Order.Status.values) - {Order.Status.EXPIRED},
        )
        self.assertTrue(
            User.objects.get(email="admin@example.com").check_password(
                "Fictional-seed-password-4729!"
            )
        )
        self.assertFalse(DatasetSnapshot.objects.exists())
        for stock in Stock.objects.all():
            total = StockMovement.objects.filter(offer_id=stock.offer_id).aggregate(
                total=Sum("quantity_delta")
            )["total"]
            self.assertEqual(stock.available_quantity, total)
        with self.assertRaises(ValueError):
            self.seed()
        self.assertEqual(Order.objects.count(), 5)

    def test_seed_refuses_historical_metadata_or_wrong_database(self):
        with self.assertRaises(ValueError):
            seed_demo(
                expected_database="olist_case_study", password="Fictional-seed-password-4729!"
            )
        from .factories import historical_records

        historical_records()
        with self.assertRaises(ValueError):
            self.seed()
        self.assertEqual(User.objects.count(), 0)

    def test_seed_rolls_back_all_partial_domain_writes(self):
        with patch(
            "orders.demo.create_order", side_effect=RuntimeError("Controlled fixture failure")
        ):
            with self.assertRaises(RuntimeError):
                self.seed()
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Stock.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_seed_rejects_short_password_before_mutation(self):
        with self.assertRaises(ValidationError):
            seed_demo(expected_database=connection.settings_dict["NAME"], password="short")
        self.assertEqual(User.objects.count(), 0)


class BenchmarkProtocolTests(TransactionTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        def november(rows):
            rows["orders"][0][3] = "2017-11-01 00:15:00"

        archive, manifest = write_fixture(self.directory.name, mutate=november)
        import_archive(
            archive=archive, manifest=manifest, expected_database=connection.settings_dict["NAME"]
        )

    def output(self, name):
        return Path(self.directory.name) / name

    def test_full_protocol_on_tiny_fixture_retains_plans_and_removes_own_index(self):
        # Only the isolated-target preflight is mocked; SQL/EXPLAIN/DDL are real PostgreSQL.
        # These miniature timings are unit-test output, never real-data benchmark evidence.
        with patch("olist.benchmark.validate_target"):
            report = run_experiment(
                expected_database="olist_benchmark", output=self.output("success")
            )
        self.assertEqual(report["status"], "SUCCEEDED")
        self.assertTrue(report["results_equivalent"])
        self.assertFalse(report["candidate_index_present_after"])
        self.assertEqual(len(list(self.output("success").glob("*measured*.json"))), 21)
        self.assertEqual(len(list(self.output("success").glob("*warmup*.json"))), 9)
        self.assertEqual(report["dataset_before"], report["dataset_after"])

    def test_failure_after_index_creation_restores_candidate_state(self):
        def fail_indexed(sql, params):
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass(%s)", [INDEX_NAME])
                if cursor.fetchone()[0] is not None:
                    raise ValueError("Controlled failure after index creation")
            return query_rows(sql, params)

        with (
            patch("olist.benchmark.validate_target"),
            patch("olist.benchmark.query_rows", side_effect=fail_indexed),
        ):
            with self.assertRaises(ValueError):
                run_experiment(expected_database="olist_benchmark", output=self.output("failure"))
        report = json.loads((self.output("failure") / "summary.json").read_text())
        self.assertEqual(report["status"], "FAILED")
        self.assertFalse(report["candidate_index_present_after"])

    def test_existing_named_index_is_preserved_on_refusal(self):
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE INDEX {INDEX_NAME} ON olist_order(source_status)")
        try:
            with patch("olist.benchmark.validate_target"), self.assertRaises(ValueError):
                run_experiment(expected_database="olist_benchmark", output=self.output("existing"))
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass(%s)", [INDEX_NAME])
                self.assertIsNotNone(cursor.fetchone()[0])
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP INDEX {INDEX_NAME}")

    def test_wrong_target_or_too_few_runs_refuse_before_mutation(self):
        with (
            patch.dict(os.environ, {"OLIST_BENCHMARK_ENABLED": "1"}),
            self.assertRaises(ValueError),
        ):
            validate_target("olist_case_study")
        with (
            patch.dict(os.environ, {"OLIST_BENCHMARK_ENABLED": "1"}),
            self.assertRaises(ValueError),
        ):
            validate_target("olist_benchmark")
        with self.assertRaises(ValueError):
            run_experiment(
                expected_database="olist_benchmark",
                output=self.output("few"),
                warmups=1,
                repetitions=3,
            )
        self.assertFalse(self.output("few").exists())

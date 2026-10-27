import tempfile
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from olist.importer import import_archive
from olist.models import (
    Category,
    HistoricalCustomer,
    HistoricalOrder,
    HistoricalOrderItem,
    HistoricalPaymentRecord,
    HistoricalProduct,
)
from olist.reports import REPORTS, execute_report, parameters

from .olist_fixture import key, write_fixture


class SQLReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.db import connection

        with tempfile.TemporaryDirectory() as temporary:
            archive, manifest = write_fixture(temporary)
            import_archive(
                archive=archive,
                manifest=manifest,
                expected_database=connection.settings_dict["NAME"],
            )
        cls.customer = HistoricalCustomer.objects.get(source_customer_id=key(1))
        cls.snapshot = cls.customer.snapshot
        HistoricalCustomer.objects.create(
            snapshot=cls.snapshot,
            source_customer_id=key(100),
            customer_unique_id=key(101),
            zip_code_prefix="00001",
            city="Fictional No-order City",
            state="SP",
        )
        cls.admin = User.objects.create_superuser(
            "admin@example.com", "Fictional-SQL-Test-472!", name="Fictional Administrator"
        )
        cls.buyer = User.objects.create_user(
            "buyer@example.com", "Fictional-SQL-Test-472!", name="Fictional Buyer"
        )

    def query(self, name, **kwargs):
        return execute_report(
            name,
            parameters(
                start="2017-03-01 00:00:00", end="2017-05-01 00:00:00", min_units=1, **kwargs
            ),
        )

    def test_independent_item_payment_aggregation_and_cancelled_exclusion(self):
        rows = self.query("monthly_sales")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["delivered_orders"], 1)
        self.assertEqual(rows[0]["merchandise_value"], Decimal("35.00"))
        self.assertEqual(rows[0]["freight_value"], Decimal("3.00"))
        self.assertEqual(rows[0]["recorded_payment_value"], Decimal("38.00"))
        self.assertEqual(len(self.query("order_details")), 3)
        product = self.query("best_selling_products")[0]
        self.assertEqual(product["units"], 3)
        self.assertEqual(product["merchandise_value"], Decimal("35.00"))

    def test_left_join_customer_coverage_preserves_no_order_and_repeat_identity(self):
        rows = self.query("customer_coverage")
        self.assertEqual(len(rows), 3)
        no_order = next(row for row in rows if row["source_customer_id"] == key(100))
        self.assertEqual(no_order["orders_all_statuses"], 0)
        self.assertEqual(len(self.query("repeat_customers")), 0)
        ranking = self.query("customer_spending")
        self.assertEqual(ranking[0]["customer_unique_id"], key(9))
        self.assertEqual(ranking[0]["observed_merchandise_value"], Decimal("35.00"))
        self.assertEqual(ranking[1]["observed_merchandise_value"], 0)

    def test_repeat_ranking_uses_unique_identity_across_source_customer_ids(self):
        order = HistoricalOrder.objects.get(source_order_id=key(7))
        order.source_status = "delivered"
        order.save(update_fields=["source_status"])
        item = HistoricalOrderItem.objects.filter(order__source_order_id=key(6)).first()
        item.pk = None
        item.order = order
        item.price = Decimal("5.00")
        item.save(force_insert=True)
        row = self.query("repeat_customers")[0]
        self.assertEqual(row["customer_unique_id"], key(9))
        self.assertEqual(row["delivered_orders"], 2)
        self.assertEqual(row["merchandise_value"], Decimal("40.00"))
        self.assertEqual(row["spending_rank"], 1)
        rate = self.query("repeat_customer_rate")[0]
        self.assertEqual(rate["eligible_customer_identities"], 1)
        self.assertEqual(rate["repeat_customer_percent"], Decimal("100.00"))

    def test_window_product_ties_share_rank_with_deterministic_display_positions(self):
        product = HistoricalProduct.objects.create(
            snapshot=self.snapshot, source_product_id=key(103)
        )
        original = HistoricalOrderItem.objects.filter(order__source_order_id=key(6)).first()
        for number in [4, 5, 6]:
            HistoricalOrderItem.objects.create(
                order_id=original.order_id,
                source_order_item_id=number,
                product=product,
                seller_id=original.seller_id,
                price="10.00",
                freight_value="0.00",
                shipping_limit_at_raw=original.shipping_limit_at_raw,
                shipping_limit_at_source=original.shipping_limit_at_source,
            )
        rows = self.query("best_selling_products")
        self.assertEqual([row["units_rank"] for row in rows], [1, 1])
        self.assertEqual([row["display_position"] for row in rows], [1, 2])

    def test_calendar_zero_months_and_running_window(self):
        rows = self.query("running_monthly_totals")
        self.assertEqual([row["observed_merchandise_value"] for row in rows], [Decimal("35.00"), 0])
        self.assertEqual(
            [row["running_observed_merchandise_value"] for row in rows],
            [Decimal("35.00"), Decimal("35.00")],
        )
        self.assertEqual(str(rows[0]["month"]), "2017-03-01")

    def test_seller_delivery_deduplicates_repeated_seller_lines_and_dates(self):
        rows = self.query("seller_delivery")
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["associated_delivered_orders"] == 1 for row in rows))
        self.assertTrue(all(row["on_time_associations"] == 1 for row in rows))
        delivery = self.query("delivery_performance")[0]
        self.assertEqual(delivery["on_time_percent"], Decimal("100.00"))
        self.assertEqual(delivery["average_signed_calendar_delay_days"], Decimal("-2"))
        HistoricalOrder.objects.filter(source_order_id=key(6)).update(
            delivered_customer_at_source=None, delivered_customer_at_raw=""
        )
        invalid = self.query("delivery_performance")[0]
        self.assertEqual(invalid["excluded_orders"], 1)
        self.assertIsNone(invalid["on_time_percent"])
        self.assertEqual(self.query("monthly_sales")[0]["merchandise_value"], Decimal("35.00"))

    def test_category_sales_and_ranked_ties(self):
        rows = self.query("category_seller_sales")
        self.assertEqual(
            {row["source_seller_id"]: row["merchandise_value"] for row in rows},
            {key(4): Decimal("15.00"), key(5): Decimal("20.00")},
        )
        self.assertEqual(rows[0]["source_category"], "untranslated_fixture")
        self.assertIsNone(rows[0]["english_category"])
        self.assertEqual(rows[0]["seller_position_within_category"], 1)
        Category.objects.filter(source_name="untranslated_fixture").update(
            english_name="Fictional Category"
        )
        self.assertEqual(
            self.query("category_seller_sales")[0]["english_category"], "Fictional Category"
        )

    def test_same_day_midnight_estimate_uses_calendar_date_in_both_delivery_reports(self):
        HistoricalOrder.objects.filter(source_order_id=key(6)).update(
            purchased_at_raw="2017-03-01 10:00:00",
            purchased_at_source=datetime(2017, 3, 1, 10),
            estimated_delivery_at_raw="2017-03-01 00:00:00",
            estimated_delivery_at_source=datetime(2017, 3, 1),
            delivered_customer_at_raw="2017-03-01 18:00:00",
            delivered_customer_at_source=datetime(2017, 3, 1, 18),
        )
        row = self.query("delivery_performance")[0]
        self.assertEqual(row["eligible_orders"], 1)
        self.assertEqual(row["on_time_orders"], 1)
        self.assertEqual(row["on_time_percent"], Decimal("100.00"))
        self.assertTrue(
            all(row["on_time_associations"] == 1 for row in self.query("seller_delivery"))
        )

    def test_reconciliation_missing_sides_and_zero_payments_are_distinct(self):
        rows = self.query("reconciliation")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["missing_items"])
        self.assertFalse(row["missing_payments"])
        self.assertEqual(row["recorded_payment"], Decimal("0.00"))
        self.assertIsNone(row["payment_minus_items_and_freight"])
        HistoricalPaymentRecord.objects.filter(order__source_order_id=key(6)).delete()
        rows = self.query("reconciliation")
        self.assertEqual(len(rows), 2)
        self.assertTrue(
            next(row for row in rows if row["source_order_id"] == key(6))["missing_payments"]
        )

    def test_empty_intervals_parameters_and_source_clock(self):
        empty = parameters(start="2020-01-01 00:00:00", end="2020-03-01 00:00:00", min_units=1)
        for name in REPORTS:
            rows = execute_report(name, empty)
            if name == "repeat_customer_rate":
                self.assertEqual(rows[0]["eligible_customer_identities"], 0)
                self.assertIsNone(rows[0]["repeat_customer_percent"])
            elif name in ["customer_coverage", "customer_spending", "running_monthly_totals"]:
                self.assertTrue(rows)
            else:
                self.assertEqual(rows, [])
        for values in [
            {"start": "2017-03-01T00:00:00Z"},
            {"start": datetime.now().astimezone()},
            {"start": "2018-01-01 00:00:00", "end": "2017-01-01 00:00:00"},
            {"min_orders": 1},
            {"min_units": True},
        ]:
            with self.assertRaises(ValidationError):
                parameters(**values)
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SET TIME ZONE 'America/Sao_Paulo'")
            try:
                self.assertEqual(self.query("monthly_sales")[0]["month"].isoformat(), "2017-03-01")
            finally:
                cursor.execute("SET TIME ZONE 'UTC'")

    def test_report_http_admin_permissions_pagination_exact_decimal_strings(self):
        client = APIClient()
        path = (
            "/api/olist/reports/monthly_sales/?start=2017-03-01%2000:00:00"
            "&end=2017-05-01%2000:00:00"
        )
        self.assertEqual(client.get(path).status_code, 401)
        client.credentials(
            HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(self.buyer).access_token)
        )
        self.assertEqual(client.get(path).status_code, 403)
        client.credentials(
            HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(self.admin).access_token)
        )
        response = client.get(path)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["recorded_payment_value"], "38.00")
        self.assertEqual(response.data["data_origin"], "OLIST_HISTORICAL")
        self.assertEqual(client.get("/api/olist/reports/unknown/").status_code, 404)
        self.assertEqual(client.get("/api/olist/reports/monthly_sales/?start=bad").status_code, 400)
        self.assertEqual(
            client.post("/api/olist/reports/monthly_sales/", {}, format="json").status_code, 405
        )

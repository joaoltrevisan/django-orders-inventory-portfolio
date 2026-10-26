from datetime import UTC, datetime
from decimal import Decimal

from django.core.exceptions import FieldError, ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.db.models.functions import TruncMonth
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from olist.models import (
    Category,
    DatasetSnapshot,
    HistoricalCustomer,
    HistoricalOrder,
    HistoricalOrderItem,
    HistoricalPaymentRecord,
    HistoricalProduct,
    ImportRun,
)

from .factories import historical_records


class HistoricalModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.snapshot, cls.customer, cls.product, cls.seller, cls.order = historical_records()

    def item(self, sequence=1):
        return HistoricalOrderItem.objects.create(
            order=self.order,
            source_order_item_id=sequence,
            product=self.product,
            seller=self.seller,
            price="10.00",
            freight_value="0.00",
            shipping_limit_at_raw="2017-03-02 00:00:00",
            shipping_limit_at_source=datetime(2017, 3, 2),
        )

    def payment(self, sequence=1):
        return HistoricalPaymentRecord.objects.create(
            order=self.order,
            payment_sequential=sequence,
            payment_type="voucher",
            payment_installments=0,
            payment_value="0.00",
        )

    def test_source_customers_are_not_login_accounts_and_repeat_identity_is_nonunique(self):
        other = HistoricalCustomer.objects.create(
            snapshot=self.snapshot,
            source_customer_id="f" * 32,
            customer_unique_id=self.customer.customer_unique_id,
            zip_code_prefix="00123",
            city="Another Fixture City",
            state="SP",
        )
        self.assertNotEqual(other.source_customer_id, self.customer.source_customer_id)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(self.customer.zip_code_prefix, "00123")
        fields = {field.name for field in HistoricalProduct._meta.fields}
        self.assertFalse(fields.intersection({"price", "name", "stock", "is_active"}))

    def test_source_customer_and_product_ids_are_unique(self):
        for model, field, value in [
            (HistoricalCustomer, "source_customer_id", self.customer.source_customer_id),
            (HistoricalProduct, "source_product_id", self.product.source_product_id),
        ]:
            with (
                self.subTest(model=model.__name__),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                original = model.objects.get(**{field: value})
                original.pk = None
                original.save(force_insert=True)

    def test_single_snapshot_enforced_by_database(self):
        for singleton in [1, 2]:
            with (
                self.subTest(singleton=singleton),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                DatasetSnapshot.objects.create(
                    singleton=singleton,
                    dataset_ref="other/fixture",
                    source_url="https://example.com",
                    reported_version="other",
                    archive_sha256="1" * 64,
                    member_manifest={},
                    mapping_version="test-1",
                    retrieved_at=timezone.now(),
                )

    def test_failed_attempt_can_exist_without_a_snapshot(self):
        run = ImportRun.objects.create(status="FAILED", counts={"imported": 0})
        self.assertIsNone(run.snapshot_id)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ImportRun.objects.create(status="UNKNOWN")

    def test_repeated_product_lines_and_multiple_payments_are_valid(self):
        self.item(1)
        self.item(2)
        self.payment(1)
        self.payment(2)
        self.assertEqual(self.order.items.count(), 2)
        self.assertEqual(self.order.payment_records.count(), 2)

    def test_source_line_and_payment_sequence_uniqueness(self):
        self.item()
        self.payment()
        for operation in [self.item, self.payment]:
            with (
                self.subTest(operation=operation.__name__),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                operation()

    def test_historical_exception_rows_are_retained(self):
        self.assertIsNone(self.order.approved_at_source)
        self.assertEqual(self.order.items.count(), 0)
        self.assertEqual(self.order.payment_records.count(), 0)
        self.order.source_status = "canceled"
        self.order.delivered_customer_at_source = datetime(2017, 3, 5)
        self.order.delivered_customer_at_raw = "2017-03-05 00:00:00"
        self.order.save()
        self.order.refresh_from_db()
        self.assertEqual(self.order.source_status, "canceled")
        self.assertIsNotNone(self.order.delivered_customer_at_source)

    def test_all_source_statuses_are_preserved_without_operational_mapping(self):
        for status in [
            "approved",
            "canceled",
            "created",
            "delivered",
            "invoiced",
            "processing",
            "shipped",
            "unavailable",
        ]:
            self.order.source_status = status
            self.order.save(update_fields=["source_status"])
            self.order.refresh_from_db()
            self.assertEqual(self.order.source_status, status)

    def test_untranslated_category_and_missing_attributes_are_valid(self):
        category = Category.objects.create(
            snapshot=self.snapshot, source_name="untranslated_source_key"
        )
        self.product.category = category
        self.product.save()
        self.assertIsNone(category.english_name)
        self.assertIsNone(self.product.weight_g)

    def test_nonfinite_negative_and_excessive_historical_money_is_rejected(self):
        item = self.item()
        payment = self.payment()
        for table, column, key in [
            ("olist_order_item", "price", item.pk),
            ("olist_order_item", "freight_value", item.pk),
            ("olist_payment_record", "payment_value", payment.pk),
        ]:
            for value in ["-0.01", "NaN", "Infinity", "100000000000000.00"]:
                with (
                    self.subTest(table=table, column=column, value=value),
                    self.assertRaises(DatabaseError),
                    transaction.atomic(),
                    connection.cursor() as cursor,
                ):
                    # Identifiers are a fixed test-owned allowlist, never request input.
                    cursor.execute(
                        f'UPDATE "{table}" SET "{column}" = %s WHERE id = %s', [value, key]
                    )
        payment.refresh_from_db()
        self.assertEqual(payment.payment_value, Decimal("0.00"))

    def test_invalid_source_key_and_postal_prefix_rejected(self):
        for field, value in [("source_customer_id", "not-an-id"), ("zip_code_prefix", "123")]:
            with self.subTest(field=field), self.assertRaises(IntegrityError), transaction.atomic():
                HistoricalCustomer.objects.filter(pk=self.customer.pk).update(**{field: value})

    def test_foreign_keys_are_checked_before_asserting_success(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            HistoricalOrder.objects.filter(pk=self.order.pk).update(customer_id=999999)
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.order.refresh_from_db()
        self.assertEqual(self.order.customer_id, self.customer.pk)

    def test_historical_references_protect_deletion(self):
        self.item()
        for obj in [self.snapshot, self.customer, self.product, self.seller, self.order]:
            with self.subTest(model=type(obj).__name__), self.assertRaises(ProtectedError):
                obj.delete()


class SourceTimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        *_, cls.order = historical_records()

    def test_native_column_type_and_raw_timestamp_are_preserved(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'olist_order' AND column_name = 'purchased_at_source'"
            )
            self.assertEqual(cursor.fetchone()[0], "timestamp without time zone")
        self.order.refresh_from_db()
        self.assertEqual(self.order.purchased_at_raw, "2017-03-01 00:15:00")
        self.assertIsNone(self.order.purchased_at_source.tzinfo)

    def test_naive_roundtrip_and_calendar_boundaries_under_non_utc_timezones(self):
        with connection.cursor() as cursor:
            cursor.execute("SHOW TimeZone")
            original = cursor.fetchone()[0]
        try:
            with timezone.override("America/Sao_Paulo"), connection.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'America/Sao_Paulo'")
                for source in [
                    datetime(2017, 3, 1, 0, 15),
                    datetime(2018, 11, 4, 0, 30),
                    datetime(2018, 2, 17, 23, 30),
                ]:
                    self.order.purchased_at_source = source
                    self.order.purchased_at_raw = source.strftime("%Y-%m-%d %H:%M:%S")
                    self.order.save()
                    self.order.refresh_from_db()
                    self.assertEqual(self.order.purchased_at_source, source)
                    cursor.execute(
                        "SELECT date_trunc('month', purchased_at_source)::date "
                        "FROM olist_order WHERE id = %s",
                        [self.order.pk],
                    )
                    self.assertEqual(cursor.fetchone()[0], source.date().replace(day=1))
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('TimeZone', %s, false)", [original])

    def test_aware_fractional_or_malformed_source_times_are_rejected(self):
        for value in [
            datetime.now(UTC),
            datetime(2017, 1, 1, microsecond=1),
            "2017-99-01 00:00:00",
            "2017-01-01T00:00:00Z",
        ]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                HistoricalOrder.objects.filter(pk=self.order.pk).update(purchased_at_source=value)

    def test_exact_and_range_queries_keep_source_calendar(self):
        self.assertEqual(
            HistoricalOrder.objects.filter(
                purchased_at_source__range=(datetime(2017, 3, 1), datetime(2017, 3, 2))
            ).count(),
            1,
        )

    def test_unsafe_inherited_orm_datetime_transforms_are_not_available(self):
        with self.assertRaises(FieldError):
            HistoricalOrder.objects.filter(purchased_at_source__year=2017).count()
        with self.assertRaises((TypeError, ValueError)):
            list(HistoricalOrder.objects.annotate(month=TruncMonth("purchased_at_source")))

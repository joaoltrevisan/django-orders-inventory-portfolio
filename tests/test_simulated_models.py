from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from catalog.models import Offer, Product, Seller
from inventory.models import Stock, StockMovement
from orders.models import Order, OrderItem

from .factories import simulated_records


class SimulatedModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.product, cls.seller, cls.offer, cls.order = simulated_records()

    def line(self, offer=None):
        return OrderItem.objects.create(
            order=self.order,
            offer=offer or self.offer,
            quantity=2,
            unit_price="12.50",
            product_sku="DEMO-001",
            product_name="Simulated product",
            seller_label="Simulated seller at purchase",
        )

    def test_same_product_can_be_bought_from_two_sellers_with_separate_stock(self):
        seller = Seller.objects.create(label="Second simulated seller")
        offer = Offer.objects.create(seller=seller, product=self.product, simulated_price="15.00")
        self.line()
        self.line(offer)
        Stock.objects.create(offer=self.offer, available_quantity=5)
        Stock.objects.create(offer=offer, available_quantity=8)
        self.assertEqual(self.order.items.count(), 2)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 5)
        self.assertEqual(Stock.objects.get(offer=offer).available_quantity, 8)

    def test_offer_and_order_line_uniqueness(self):
        self.line()
        for operation in [
            self.line,
            lambda: Offer.objects.create(
                seller=self.seller, product=self.product, simulated_price="2.00"
            ),
        ]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                operation()

    def test_offer_reassignment_rejected_through_bulk_and_raw_sql(self):
        product = Product.objects.create(sku="DEMO-002", name="Another fictional product")
        seller = Seller.objects.create(label="Another simulated seller")
        for field, value in [("product_id", product.pk), ("seller_id", seller.pk)]:
            with (
                self.subTest(path="ORM", field=field),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                Offer.objects.filter(pk=self.offer.pk).update(**{field: value})
            with (
                self.subTest(path="SQL", field=field),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    f'UPDATE catalog_offer SET "{field}" = %s WHERE id = %s', [value, self.offer.pk]
                )

    def test_reprice_and_deactivate_preserve_purchase_snapshots(self):
        line = self.line()
        self.offer.simulated_price = Decimal("99.00")
        self.offer.is_active = False
        self.offer.save()
        self.product.name = "Renamed simulated product"
        self.product.save()
        line.refresh_from_db()
        self.assertEqual(line.unit_price, Decimal("12.50"))
        self.assertEqual(line.subtotal, Decimal("25.00"))
        self.assertEqual(line.product_name, "Simulated product")
        self.assertEqual(line.seller_label, "Simulated seller at purchase")

    def test_simulated_price_must_be_positive_finite(self):
        for price in ["0", "-0.01", "NaN"]:
            with (
                self.subTest(price=price),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    "UPDATE catalog_offer SET simulated_price = %s WHERE id = %s",
                    [price, self.offer.pk],
                )

    def test_stock_cannot_be_negative_and_is_unique_per_offer(self):
        stock = Stock.objects.create(offer=self.offer, available_quantity=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Stock.objects.filter(pk=stock.pk).update(available_quantity=-1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Stock.objects.create(offer=self.offer)

    def test_quantities_reject_zero_and_fractional_or_boolean_inputs(self):
        line = self.line()
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.filter(pk=line.pk).update(quantity=0)
        for value in [True, 1.5, Decimal("1.5")]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                OrderItem.objects.filter(pk=line.pk).update(quantity=value)

    def test_movement_sign_order_and_duplicate_effect_constraints(self):
        StockMovement.objects.create(
            offer=self.offer,
            order=self.order,
            performed_by=self.user,
            movement_type="RESERVATION",
            quantity_delta=-2,
            reason="Simulated purchase fixture",
        )
        for movement_type, delta, order in [
            ("RESERVATION", -2, self.order),
            ("ENTRY", -1, None),
            ("ENTRY", 1, self.order),
            ("RELEASE", -2, self.order),
            ("ADJUSTMENT", 0, None),
            ("UNKNOWN", 1, None),
        ]:
            with (
                self.subTest(kind=movement_type, delta=delta),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                StockMovement.objects.create(
                    offer=self.offer,
                    order=order,
                    performed_by=self.user,
                    movement_type=movement_type,
                    quantity_delta=delta,
                    reason="Constraint probe",
                )
        StockMovement.objects.create(
            offer=self.offer,
            order=self.order,
            performed_by=self.user,
            movement_type="RELEASE",
            quantity_delta=2,
            reason="Simulated release fixture",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockMovement.objects.create(
                offer=self.offer,
                order=self.order,
                performed_by=self.user,
                movement_type="RELEASE",
                quantity_delta=2,
                reason="Duplicate release probe",
            )

    def test_invalid_status_timestamp_combination_rejected(self):
        for changes in [
            {"status": "INVALID"},
            {"status": "PAID"},
            {"currency": "USD"},
            {"total": "0.00"},
        ]:
            with (
                self.subTest(changes=changes),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                Order.objects.filter(pk=self.order.pk).update(**changes)

    def test_offer_order_and_actor_references_protect_history(self):
        self.line()
        for obj in [self.offer, self.order, self.user, self.product, self.seller]:
            with self.subTest(model=type(obj).__name__), self.assertRaises(ProtectedError):
                obj.delete()

    def test_django_password_hashing_and_case_insensitive_email_uniqueness(self):
        self.assertNotEqual(self.user.password, "test-fixture-password")
        self.assertTrue(self.user.check_password("test-fixture-password"))
        self.assertEqual(User.objects.get_by_natural_key(" CUSTOMER@EXAMPLE.COM "), self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(
                email="CUSTOMER@EXAMPLE.COM", name="Duplicate fixture", password="unusable"
            )

    def test_jwt_dependency_roundtrip_smoke_only(self):
        token = AccessToken.for_user(self.user)
        decoded = AccessToken(str(token))
        self.assertEqual(decoded["user_id"], str(self.user.pk))
        self.assertEqual(decoded["aud"], "marketplace-operations-api")
        self.assertEqual(decoded["iss"], "marketplace-operations-api")

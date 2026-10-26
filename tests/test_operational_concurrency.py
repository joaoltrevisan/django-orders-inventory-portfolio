from decimal import Decimal

from django.db import DatabaseError, connection, transaction
from django.db.models import Sum
from django.test import TransactionTestCase, override_settings

from catalog.models import Product
from catalog.services import save_offer, save_seller
from inventory.models import Stock, StockMovement
from inventory.services import change_stock
from orders.exceptions import OrderConflict
from orders.lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from orders.models import Order, OrderItem, SimulatedPayment
from orders.services import create_order

from .controlled_concurrency import ControlledConcurrencyMixin
from .operational_fixture import ADDRESS, operational_fixture


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class OperationalConcurrencyTests(ControlledConcurrencyMixin, TransactionTestCase):
    # Fast hashing is limited to non-authentication concurrency fixtures, never runtime accounts.
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        with connection.cursor() as cursor:
            cursor.execute("SHOW transaction_isolation")
            self.assertEqual(cursor.fetchone()[0], "read committed")
        operational_fixture(self)

    def buy(self, actor=None, items=None):
        return create_order(
            actor=actor or self.buyer,
            items=items or [{"offer_id": self.offer.pk, "quantity": 1}],
            shipping_address=dict(ADDRESS),
        )

    def stock(self, delta):
        return change_stock(
            actor=self.admin,
            offer_id=self.offer.pk,
            movement_type="ADJUSTMENT",
            quantity_delta=delta,
            reason="Controlled fictional race.",
        )

    def capture(self, operation):
        def run(*_):
            try:
                return "ok", operation()
            except OrderConflict as error:
                return "conflict", error.code

        return run

    def race(self, left, right, *, pause='UPDATE "orders_order"'):
        return self.run_contended(
            self.capture(left), self.capture(right), pause_before=lambda sql: sql.startswith(pause)
        )

    def assert_ledger(self):
        for stock in Stock.objects.all():
            total = (
                StockMovement.objects.filter(offer_id=stock.offer_id).aggregate(
                    total=Sum("quantity_delta")
                )["total"]
                or 0
            )
            self.assertEqual(stock.available_quantity, total)

    def test_last_unit_is_purchased_once_after_a_real_lock_wait(self):
        self.stock(-9)
        first, second = self.race(
            self.buy, lambda: self.buy(actor=self.other), pause='INSERT INTO "orders_order"'
        )
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "insufficient_stock"))
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 0)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 1)
        self.assert_ledger()

    def test_reversed_multi_seller_multi_product_inputs_use_common_lock_order(self):
        second_product = Product.objects.create(sku="OP-002", name="Simulated Desk")
        second = save_offer(
            actor=self.admin,
            data={
                "seller_id": self.second_seller.pk,
                "product_id": second_product.pk,
                "simulated_price": "5.00",
            },
        )
        change_stock(
            actor=self.admin,
            offer_id=second.pk,
            movement_type="ENTRY",
            quantity_delta=2,
            reason="Fictional second product supply.",
        )
        items = [{"offer_id": self.offer.pk, "quantity": 1}, {"offer_id": second.pk, "quantity": 1}]
        results = self.race(
            lambda: self.buy(items=items),
            lambda: self.buy(actor=self.other, items=list(reversed(items))),
            pause='INSERT INTO "orders_order"',
        )
        self.assertEqual([r[0] for r in results], ["ok", "ok"])
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(OrderItem.objects.count(), 4)
        self.assertEqual(Stock.objects.get(offer=second).available_quantity, 0)
        self.assert_ledger()

    def test_rolled_back_first_reservation_releases_units_to_waiting_customer(self):
        self.stock(-9)

        def first_purchase():
            def fail(execute, sql, params, many, context):
                result = execute(sql, params, many, context)
                if sql.startswith('INSERT INTO "inventory_stock_movement"'):
                    raise DatabaseError("Controlled failure after a real ledger insert.")
                return result

            with connection.execute_wrapper(fail):
                try:
                    self.buy()
                except DatabaseError:
                    return "rolled_back"
            raise AssertionError("The injected failure did not occur.")

        first, second = self.race(
            first_purchase, lambda: self.buy(actor=self.other), pause='INSERT INTO "orders_order"'
        )
        self.assertEqual(first, ("ok", "rolled_back"))
        self.assertEqual(second[0], "ok")
        self.assertEqual(Order.objects.get().customer.user_id, self.other.pk)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 1)
        self.assert_ledger()

    def test_two_cancellations_release_once_and_preserve_the_first_actor(self):
        order = self.buy()
        results = self.race(
            lambda: cancel_order(actor=self.admin, order_id=order.pk),
            lambda: cancel_order(actor=self.buyer, order_id=order.pk),
        )
        self.assertEqual([r[0] for r in results], ["ok", "ok"])
        self.assertEqual(results[0][1].order.updated_at, results[1][1].order.updated_at)
        self.assertEqual(results[0][1].order.cancelled_at, results[1][1].order.cancelled_at)
        self.assertEqual(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").count(), 1
        )
        self.assertEqual(
            StockMovement.objects.get(order=order, movement_type="RELEASE").performed_by_id,
            self.admin.pk,
        )
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        self.assert_ledger()

    def test_payment_wins_and_waiting_cancellation_is_rejected(self):
        order = self.buy()
        first, second = self.race(
            lambda: approve_simulated_payment(actor=self.admin, order_id=order.pk),
            lambda: cancel_order(actor=self.buyer, order_id=order.pk),
        )
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "invalid_transition"))
        self.assertEqual(Order.objects.get().status, "PAID")
        self.assertEqual(SimulatedPayment.objects.count(), 1)
        self.assertFalse(StockMovement.objects.filter(movement_type="RELEASE").exists())
        self.assert_ledger()

    def test_cancellation_wins_and_waiting_payment_is_rejected(self):
        order = self.buy()
        first, second = self.race(
            lambda: cancel_order(actor=self.buyer, order_id=order.pk),
            lambda: approve_simulated_payment(actor=self.admin, order_id=order.pk),
        )
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "invalid_transition"))
        self.assertEqual(Order.objects.get().status, "CANCELLED")
        self.assertFalse(SimulatedPayment.objects.exists())
        self.assert_ledger()

    def test_simultaneous_payment_repetitions_keep_one_reference(self):
        order = self.buy()

        def action():
            return approve_simulated_payment(actor=self.admin, order_id=order.pk)

        first, second = self.race(action, action)
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(
            first[1].simulated_payment.reference, second[1].simulated_payment.reference
        )
        self.assertEqual(first[1].order.updated_at, second[1].order.updated_at)
        self.assertEqual(SimulatedPayment.objects.count(), 1)
        self.assert_ledger()

    def test_shipping_and_waiting_delivery_return_coherent_action_snapshots(self):
        order = self.buy()
        approve_simulated_payment(actor=self.admin, order_id=order.pk)
        first, second = self.race(
            lambda: ship_order(actor=self.admin, order_id=order.pk, tracking_code="SIMULATED-1"),
            lambda: deliver_order(actor=self.admin, order_id=order.pk),
        )
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(first[1].order.status, "SHIPPED")
        self.assertIsNone(first[1].shipment.delivered_at)
        self.assertEqual(second[1].order.status, "DELIVERED")
        self.assertIsNotNone(second[1].shipment.delivered_at)
        self.assertEqual(first[1].shipment.pk, second[1].shipment.pk)
        self.assert_ledger()

    def test_repricing_first_makes_waiting_purchase_use_the_new_committed_price(self):
        first, second = self.race(
            lambda: save_offer(
                actor=self.admin, pk=self.offer.pk, data={"simulated_price": "30.00"}
            ),
            self.buy,
            pause='UPDATE "catalog_offer"',
        )
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(Order.objects.get().total, Decimal("30.00"))
        self.assertEqual(OrderItem.objects.get().unit_price, Decimal("30.00"))
        self.assert_ledger()

    def test_purchase_first_preserves_original_price_while_catalog_update_waits(self):
        first, second = self.race(
            self.buy,
            lambda: save_offer(
                actor=self.admin, pk=self.offer.pk, data={"simulated_price": "30.00"}
            ),
            pause='INSERT INTO "orders_order"',
        )
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(Order.objects.get().total, Decimal("12.50"))
        self.assertEqual(OrderItem.objects.get().unit_price, Decimal("12.50"))
        self.assert_ledger()

    def test_seller_deactivation_first_blocks_waiting_purchase(self):
        first, second = self.race(
            lambda: save_seller(actor=self.admin, pk=self.seller.pk, data={"is_active": False}),
            self.buy,
            pause='UPDATE "catalog_seller"',
        )
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "offer_inactive"))
        self.assertFalse(Order.objects.exists())
        self.assert_ledger()

    def test_two_inventory_adjustments_accumulate_without_lost_updates(self):
        first, second = self.race(
            lambda: self.stock(-3), lambda: self.stock(5), pause='UPDATE "inventory_stock"'
        )
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 12)
        self.assert_ledger()

    def test_adjustment_first_forces_waiting_purchase_to_recheck_stock(self):
        first, second = self.race(
            lambda: self.stock(-10), self.buy, pause='UPDATE "inventory_stock"'
        )
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "insufficient_stock"))
        self.assertFalse(Order.objects.exists())
        self.assert_ledger()

    def test_different_orders_cancel_overlapping_offers_without_inverse_order_locks(self):
        items = [
            {"offer_id": self.offer.pk, "quantity": 2},
            {"offer_id": self.second_offer.pk, "quantity": 1},
        ]
        first_order = self.buy(items=items)
        second_order = self.buy(actor=self.other, items=list(reversed(items)))
        first, second = self.race(
            lambda: cancel_order(actor=self.buyer, order_id=first_order.pk),
            lambda: cancel_order(actor=self.other, order_id=second_order.pk),
        )
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(StockMovement.objects.filter(movement_type="RELEASE").count(), 4)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        self.assertEqual(Stock.objects.get(offer=self.second_offer).available_quantity, 5)
        self.assert_ledger()

    def test_purchase_explicitly_locks_stock_rows_before_deducting(self):
        def hold_stock(locked, release):
            with transaction.atomic():
                stock = Stock.objects.select_for_update().get(offer=self.offer)
                # A test probe with no writes/FKs; it never acquires parents afterward.
                locked.set()
                if not release.wait(8):
                    raise TimeoutError("The test did not release its stock probe.")
            return stock.pk

        first, second = self.run_contended(
            hold_stock, self.capture(self.buy), wait_table="inventory_stock"
        )
        self.assertEqual(second[0], "ok")
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 9)
        self.assert_ledger()

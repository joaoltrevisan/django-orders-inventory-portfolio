from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection
from django.db.models import Sum
from django.http import Http404
from django.test import TestCase

from accounts.models import User
from catalog.models import Offer, Product, Seller
from catalog.services import save_offer, save_product, save_seller
from common.limits import MAX_ORDER_ITEMS, MAX_STOCK_QUANTITY
from inventory.models import Stock, StockMovement
from inventory.services import change_stock
from orders.exceptions import OrderConflict, OrderIntegrityConflict
from orders.lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from orders.models import Order, OrderItem, Shipment, SimulatedPayment
from orders.services import create_order

from .operational_fixture import ADDRESS, operational_fixture


class OperationalServicesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        operational_fixture(cls)

    def buy(self, items=None, actor=None):
        return create_order(
            actor=actor or self.buyer,
            items=items if items is not None else [{"offer_id": self.offer.pk, "quantity": 3}],
            shipping_address=dict(ADDRESS),
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

    def test_multi_seller_same_product_purchase_snapshots_and_server_total(self):
        order = self.buy(
            [
                {"offer_id": self.second_offer.pk, "quantity": 2},
                {"offer_id": self.offer.pk, "quantity": 3},
            ]
        )
        self.assertEqual(order.total, Decimal("77.50"))
        self.assertEqual(order.status, "PENDING_PAYMENT")
        self.assertEqual(order.customer.user_id, self.buyer.pk)
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(
            list(order.items.order_by("offer_id").values_list("seller_label", flat=True)),
            ["Simulated Seller One", "Simulated Seller Two"],
        )
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 7)
        self.assertEqual(Stock.objects.get(offer=self.second_offer).available_quantity, 3)
        self.assertEqual(
            StockMovement.objects.filter(
                order=order, movement_type="RESERVATION", performed_by=self.buyer
            ).count(),
            2,
        )
        self.assert_ledger()

    def test_last_line_insufficient_stock_leaves_no_order_or_partial_reservation(self):
        with self.assertRaises(OrderConflict) as error:
            self.buy(
                [
                    {"offer_id": self.offer.pk, "quantity": 2},
                    {"offer_id": self.second_offer.pk, "quantity": 6},
                ]
            )
        self.assertEqual(error.exception.code, "insufficient_stock")
        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.assertEqual(StockMovement.objects.count(), 2)
        self.assert_ledger()

    def test_error_after_actual_reservation_insert_rolls_back_all_writes(self):
        def fail(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if sql.startswith('INSERT INTO "inventory_stock_movement"'):
                raise DatabaseError("Private fixture failure after inserted ledger.")
            return result

        with connection.execute_wrapper(fail), self.assertRaises(DatabaseError):
            self.buy()
        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        self.assertEqual(StockMovement.objects.count(), 2)
        self.assert_ledger()

    def test_input_limits_duplicates_and_direct_service_validation(self):
        for items in [
            [],
            [{"offer_id": self.offer.pk, "quantity": quantity} for quantity in [1, 2]],
            [{"offer_id": self.offer.pk, "quantity": 1}] * (MAX_ORDER_ITEMS + 1),
            [{"offer_id": True, "quantity": 1}],
        ]:
            with self.subTest(items=items[:2]), self.assertRaises(ValidationError):
                self.buy(items)
        for quantity in [0, -1, True, 1.5, "2", None, 10000]:
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.buy([{"offer_id": self.offer.pk, "quantity": quantity}])
        for address in [
            {},
            {**ADDRESS, "country": "US"},
            {**ADDRESS, "postal_code": "123"},
            {**ADDRESS, "street": "\x00"},
        ]:
            with self.assertRaises(ValidationError):
                create_order(
                    actor=self.buyer,
                    items=[{"offer_id": self.offer.pk, "quantity": 1}],
                    shipping_address=address,
                )
        self.assertFalse(Order.objects.exists())

    def test_missing_uninitialized_and_inactive_offer_parents_refuse_purchase(self):
        with self.assertRaises(OrderConflict):
            self.buy([{"offer_id": 999999, "quantity": 1}])
        for model, pk in [
            (Offer, self.offer.pk),
            (Product, self.product.pk),
            (Seller, self.seller.pk),
        ]:
            model.objects.filter(pk=pk).update(is_active=False)
            with self.assertRaises(OrderConflict) as error:
                self.buy()
            self.assertEqual(error.exception.code, "offer_inactive")
            model.objects.filter(pk=pk).update(is_active=True)
        Stock.objects.filter(offer=self.offer).delete()
        with self.assertRaises(OrderConflict) as error:
            self.buy()
        self.assertEqual(error.exception.code, "stock_unavailable")
        self.assertFalse(Order.objects.exists())

    def test_snapshots_survive_catalog_edits_and_inactive_catalog_cancellation(self):
        order = self.buy()
        save_offer(
            actor=self.admin,
            pk=self.offer.pk,
            data={"simulated_price": "99.90", "is_active": False},
        )
        save_product(
            actor=self.admin,
            pk=self.product.pk,
            data={"name": "Renamed Product", "is_active": False},
        )
        save_seller(
            actor=self.admin,
            pk=self.seller.pk,
            data={"label": "Renamed Seller", "is_active": False},
        )
        line = order.items.get()
        self.assertEqual(
            (line.product_name, line.seller_label, line.unit_price),
            ("Simulated Lamp", "Simulated Seller One", Decimal("12.50")),
        )
        result = cancel_order(actor=self.buyer, order_id=order.pk)
        self.assertEqual(result.order.status, "CANCELLED")
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        self.assert_ledger()

    def test_cancellation_repetition_restores_once_and_preserves_timestamps(self):
        order = self.buy(
            [
                {"offer_id": self.offer.pk, "quantity": 3},
                {"offer_id": self.second_offer.pk, "quantity": 2},
            ]
        )
        first = cancel_order(actor=self.buyer, order_id=order.pk)
        second = cancel_order(actor=self.admin, order_id=order.pk)
        self.assertEqual(first.order.cancelled_at, second.order.cancelled_at)
        self.assertEqual(first.order.updated_at, second.order.updated_at)
        self.assertEqual(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").count(), 2
        )
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        self.assertEqual(Stock.objects.get(offer=self.second_offer).available_quantity, 5)
        self.assert_ledger()

    def test_admin_can_cancel_inactive_customer_and_actor_history_survives_role_change(self):
        order = self.buy()
        User.objects.filter(pk=self.buyer.pk).update(is_active=False)
        cancel_order(actor=self.admin, order_id=order.pk)
        self.assertEqual(
            order.stock_movements.get(movement_type="RELEASE").performed_by_id, self.admin.pk
        )
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        User.objects.filter(pk=self.buyer.pk).update(is_active=True)
        self.assertEqual(
            cancel_order(actor=self.buyer, order_id=order.pk).order.status, "CANCELLED"
        )
        self.assert_ledger()

    def test_cancellation_failure_after_status_write_rolls_back_release_and_stock(self):
        order = self.buy()

        def fail(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if sql.startswith('UPDATE "orders_order"'):
                raise DatabaseError("Private simulated cancellation failure.")
            return result

        with connection.execute_wrapper(fail), self.assertRaises(DatabaseError):
            cancel_order(actor=self.buyer, order_id=order.pk)
        order.refresh_from_db()
        self.assertEqual(order.status, "PENDING_PAYMENT")
        self.assertFalse(order.stock_movements.filter(movement_type="RELEASE").exists())
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 7)
        self.assert_ledger()

    def test_complete_lifecycle_repeats_are_stable_and_do_not_change_stock(self):
        order = self.buy()
        paid = approve_simulated_payment(actor=self.admin, order_id=order.pk)
        self.assertEqual(paid.simulated_payment.amount, Decimal("37.50"))
        self.assertTrue(paid.simulated_payment.is_simulated)
        repeat = approve_simulated_payment(actor=self.admin, order_id=order.pk)
        self.assertEqual(paid.simulated_payment.reference, repeat.simulated_payment.reference)
        self.assertEqual(paid.order.updated_at, repeat.order.updated_at)
        shipped = ship_order(actor=self.admin, order_id=order.pk, tracking_code="SIMULATED-TRACK-1")
        repeat_ship = ship_order(
            actor=self.admin, order_id=order.pk, tracking_code="SIMULATED-TRACK-1"
        )
        self.assertEqual(shipped.order.updated_at, repeat_ship.order.updated_at)
        delivered = deliver_order(actor=self.admin, order_id=order.pk)
        repeated = deliver_order(actor=self.admin, order_id=order.pk)
        self.assertEqual(delivered.order.delivered_at, repeated.order.delivered_at)
        self.assertEqual(delivered.order.updated_at, repeated.order.updated_at)
        self.assertEqual(delivered.shipment.pk, shipped.shipment.pk)
        self.assertEqual(SimulatedPayment.objects.count(), 1)
        self.assertEqual(Shipment.objects.count(), 1)
        self.assertEqual(order.stock_movements.count(), 1)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 7)
        self.assert_ledger()

    def test_invalid_transitions_and_conflicting_repeat_tracking(self):
        order = self.buy()
        for action in [ship_order, deliver_order]:
            with self.assertRaises(OrderConflict):
                action(actor=self.admin, order_id=order.pk)
        approve_simulated_payment(actor=self.admin, order_id=order.pk)
        with self.assertRaises(OrderConflict):
            cancel_order(actor=self.buyer, order_id=order.pk)
        with self.assertRaises(OrderConflict):
            deliver_order(actor=self.admin, order_id=order.pk)
        ship_order(actor=self.admin, order_id=order.pk, tracking_code="FIRST")
        with self.assertRaises(OrderConflict) as error:
            ship_order(actor=self.admin, order_id=order.pk, tracking_code="DIFFERENT")
        self.assertEqual(error.exception.code, "tracking_conflict")
        second = self.buy()
        cancel_order(actor=self.buyer, order_id=second.pk)
        for action in [approve_simulated_payment, ship_order, deliver_order]:
            with self.assertRaises(OrderConflict):
                action(actor=self.admin, order_id=second.pk)
        self.assert_ledger()

    def test_payment_failure_rolls_back_associated_record(self):
        order = self.buy()
        with (
            patch("orders.lifecycle.Order.save", side_effect=DatabaseError("Private failure")),
            self.assertRaises(DatabaseError),
        ):
            approve_simulated_payment(actor=self.admin, order_id=order.pk)
        self.assertFalse(SimulatedPayment.objects.exists())
        order.refresh_from_db()
        self.assertEqual(order.status, "PENDING_PAYMENT")

    def test_corrupted_order_ledger_totals_payment_and_shipment_are_never_repaired(self):
        order = self.buy()
        Order.objects.filter(pk=order.pk).update(total="1.00")
        with self.assertRaises(OrderIntegrityConflict):
            cancel_order(actor=self.buyer, order_id=order.pk)
        Order.objects.filter(pk=order.pk).update(total="37.50")
        reserve = order.stock_movements.get()
        StockMovement.objects.filter(pk=reserve.pk).update(quantity_delta=-2)
        with self.assertRaises(OrderIntegrityConflict):
            cancel_order(actor=self.buyer, order_id=order.pk)
        StockMovement.objects.filter(pk=reserve.pk).update(quantity_delta=-3)
        approve_simulated_payment(actor=self.admin, order_id=order.pk)
        SimulatedPayment.objects.filter(order=order).update(amount="1.00")
        with self.assertRaises(OrderIntegrityConflict):
            approve_simulated_payment(actor=self.admin, order_id=order.pk)
        SimulatedPayment.objects.filter(order=order).update(amount="37.50")
        ship_order(actor=self.admin, order_id=order.pk)
        Shipment.objects.filter(order=order).delete()
        with self.assertRaises(OrderIntegrityConflict):
            deliver_order(actor=self.admin, order_id=order.pk)
        self.assertFalse(StockMovement.objects.filter(movement_type="RELEASE").exists())

    def test_corrupted_cancelled_release_blocks_repeated_success(self):
        order = self.buy()
        cancel_order(actor=self.buyer, order_id=order.pk)
        order.stock_movements.filter(movement_type="RELEASE").update(quantity_delta=2)
        with self.assertRaises(OrderIntegrityConflict):
            cancel_order(actor=self.buyer, order_id=order.pk)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)

    def test_inventory_validation_underflow_ledger_consistency_and_late_failure(self):
        for kind, delta, reason in [
            ("ENTRY", -1, "Example"),
            ("ADJUSTMENT", 0, "Example"),
            ("ADJUSTMENT", True, "Example"),
            ("RESERVATION", 1, "Example"),
            ("ENTRY", 1, " "),
        ]:
            with self.assertRaises(ValidationError):
                change_stock(
                    actor=self.admin,
                    offer_id=self.offer.pk,
                    movement_type=kind,
                    quantity_delta=delta,
                    reason=reason,
                )
        with self.assertRaises(OrderConflict):
            change_stock(
                actor=self.admin,
                offer_id=self.offer.pk,
                movement_type="ADJUSTMENT",
                quantity_delta=-11,
                reason="Cannot remove unavailable units.",
            )
        with (
            patch(
                "inventory.services.StockMovement.objects.create",
                side_effect=DatabaseError("Private failure"),
            ),
            self.assertRaises(DatabaseError),
        ):
            change_stock(
                actor=self.admin,
                offer_id=self.offer.pk,
                movement_type="ENTRY",
                quantity_delta=5,
                reason="Atomic entry fixture.",
            )
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        Stock.objects.filter(offer=self.offer).update(available_quantity=9)
        with self.assertRaises(OrderIntegrityConflict):
            self.buy()
        with self.assertRaises(OrderIntegrityConflict):
            change_stock(
                actor=self.admin,
                offer_id=self.offer.pk,
                movement_type="ENTRY",
                quantity_delta=1,
                reason="No silent ledger repair.",
            )

    def test_headroom_boundary_preserves_cancellation_and_payment_frees_capacity(self):
        order = self.buy()
        change_stock(
            actor=self.admin,
            offer_id=self.offer.pk,
            movement_type="ENTRY",
            quantity_delta=MAX_STOCK_QUANTITY - 10,
            reason="Boundary fixture, not physical stock.",
        )
        with self.assertRaises(OrderConflict):
            change_stock(
                actor=self.admin,
                offer_id=self.offer.pk,
                movement_type="ENTRY",
                quantity_delta=1,
                reason="Would consume cancellation capacity.",
            )
        cancel_order(actor=self.admin, order_id=order.pk)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, MAX_STOCK_QUANTITY)
        other = self.buy()
        approve_simulated_payment(actor=self.admin, order_id=other.pk)
        change_stock(
            actor=self.admin,
            offer_id=self.offer.pk,
            movement_type="ENTRY",
            quantity_delta=3,
            reason="Paid purchase no longer needs cancellation capacity.",
        )
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, MAX_STOCK_QUANTITY)
        self.assert_ledger()

    def test_direct_service_permissions_and_foreign_order_isolation(self):
        order = self.buy()
        with self.assertRaises(PermissionDenied):
            self.buy(actor=self.admin)
        with self.assertRaises(Http404):
            cancel_order(actor=self.other, order_id=order.pk)
        for action in [approve_simulated_payment, ship_order, deliver_order]:
            with self.assertRaises(PermissionDenied):
                action(actor=self.buyer, order_id=order.pk)
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        with self.assertRaises(PermissionDenied):
            change_stock(
                actor=self.admin,
                offer_id=self.offer.pk,
                movement_type="ENTRY",
                quantity_delta=1,
                reason="Revoked actor.",
            )

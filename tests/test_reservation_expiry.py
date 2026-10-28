"""PostgreSQL expiry boundaries, audit history, partial batches and observed races."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from queue import Queue
from threading import Event
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import (
    DatabaseError,
    IntegrityError,
    close_old_connections,
    connection,
    connections,
    transaction,
)
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.locking import lock_offer_inventory
from catalog.models import Offer, Product, Seller
from common.limits import MAX_STOCK_QUANTITY
from inventory.models import Stock, StockMovement
from inventory.services import change_stock
from orders.exceptions import OrderConflict
from orders.lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from orders.models import Order, SimulatedPayment
from orders.reservations import database_now, expire_due_reservations
from orders.services import create_order

from .controlled_concurrency import ControlledConcurrencyMixin
from .operational_fixture import ADDRESS, operational_fixture


class ReservationExpiryFixture:
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        operational_fixture(self)

    def buy(self, *, multi=False, key=None):
        items = [{"offer_id": self.offer.pk, "quantity": 1}]
        if multi:
            items.append({"offer_id": self.second_offer.pk, "quantity": 2})
        return create_order(
            actor=self.buyer, items=items, shipping_address=dict(ADDRESS), idempotency_key=key
        )

    def due(self, order):
        # Test-only time travel: preserve a coherent purchase/reservation chronology.
        created = timezone.now() - timedelta(hours=1)
        Order.objects.filter(pk=order.pk).update(
            created_at=created, reservation_expires_at=created + timedelta(minutes=30)
        )
        StockMovement.objects.filter(order=order).update(
            created_at=created + timedelta(microseconds=1)
        )
        order.refresh_from_db()
        return order

    def sweep(self, **kwargs):
        return expire_due_reservations(actor=self.admin, **kwargs)

    def client_for(self, actor):
        client = APIClient()
        client.force_authenticate(actor)
        return client


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ReservationExpiryTests(ReservationExpiryFixture, TransactionTestCase):
    def test_deadline_is_exact_and_client_cannot_override_it(self):
        order = self.buy()
        self.assertEqual(order.reservation_expires_at, order.created_at + timedelta(minutes=30))
        self.assertIsNone(order.expired_at)
        response = self.client_for(self.buyer).post(
            "/api/orders/",
            {
                "items": [{"offer_id": self.offer.pk, "quantity": 1}],
                "shipping_address": ADDRESS,
                "reservation_expires_at": order.reservation_expires_at.isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        with CaptureQueriesContext(connection) as captured:
            self.assertTrue(timezone.is_aware(database_now()))
        self.assertIn("clock_timestamp()", captured[0]["sql"])

    def test_payment_strict_before_equal_after_boundary(self):
        for delta in [-1, 0, 1]:
            with self.subTest(microseconds=delta):
                order = self.buy()
                at = order.reservation_expires_at + timedelta(microseconds=delta)
                with patch("orders.lifecycle.database_now", return_value=at):
                    if delta < 0:
                        result = approve_simulated_payment(actor=self.admin, order_id=order.pk)
                        self.assertEqual(result.order.paid_at, at)
                    else:
                        with self.assertRaises(OrderConflict) as error:
                            approve_simulated_payment(actor=self.admin, order_id=order.pk)
                        self.assertEqual(error.exception.code, "reservation_expired")
                        order.refresh_from_db()
                        self.assertEqual(order.status, "PENDING_PAYMENT")
                        self.assertFalse(SimulatedPayment.objects.filter(order=order).exists())

    def test_legacy_null_deadline_remains_payable_and_not_swept(self):
        order = self.due(self.buy())
        Order.objects.filter(pk=order.pk).update(reservation_expires_at=None)
        self.assertEqual(self.sweep()["attempted_order_ids"], [])
        self.assertEqual(
            approve_simulated_payment(actor=self.admin, order_id=order.pk).order.status, "PAID"
        )

    def test_overdue_payment_refusal_does_not_release_or_autoexpire(self):
        order = self.due(self.buy())
        response = self.client_for(self.admin).post(
            f"/api/orders/{order.pk}/simulated-payment/", {}, format="json"
        )
        self.assertEqual(
            (response.status_code, response.data["code"]), (409, "reservation_expired")
        )
        order.refresh_from_db()
        self.assertEqual(order.status, "PENDING_PAYMENT")
        self.assertIsNone(order.expired_at)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 9)
        self.assertFalse(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").exists()
        )

    def test_multi_offer_expiry_audited_once_despite_inactive_customer_catalog(self):
        order = self.due(self.buy(multi=True))
        User.objects.filter(pk=self.buyer.pk).update(is_active=False)
        Product.objects.update(is_active=False)
        Seller.objects.update(is_active=False)
        Offer.objects.update(is_active=False)
        result = self.sweep()
        self.assertEqual(result["expired_order_ids"], [order.pk])
        order.refresh_from_db()
        expired_at = order.expired_at
        self.assertEqual(order.status, "EXPIRED")
        self.assertGreaterEqual(expired_at, order.reservation_expires_at)
        self.assertIsNone(order.cancelled_at)
        releases = StockMovement.objects.filter(order=order, movement_type="RELEASE")
        self.assertEqual(releases.count(), 2)
        self.assertEqual(set(releases.values_list("performed_by_id", flat=True)), {self.admin.pk})
        self.assertTrue(all("expiry" in m.reason for m in releases))
        self.assertEqual(
            [
                Stock.objects.get(offer=o).available_quantity
                for o in [self.offer, self.second_offer]
            ],
            [10, 5],
        )
        self.assertEqual(self.sweep()["attempted_order_ids"], [])
        order.refresh_from_db()
        self.assertEqual(order.expired_at, expired_at)

    def test_live_paid_cancelled_orders_are_not_expired(self):
        self.buy()
        paid = self.buy()
        approve_simulated_payment(actor=self.admin, order_id=paid.pk)
        cancelled = self.due(self.buy())
        cancel_order(actor=self.buyer, order_id=cancelled.pk)
        self.assertEqual(self.sweep()["attempted_order_ids"], [])

    def test_overdue_customer_cancellation_still_wins_and_repeats(self):
        order = self.due(self.buy())
        first = cancel_order(actor=self.buyer, order_id=order.pk)
        second = cancel_order(actor=self.buyer, order_id=order.pk)
        self.assertEqual(first.order.cancelled_at, second.order.cancelled_at)
        self.assertEqual(self.sweep()["expired_order_ids"], [])
        self.assertEqual(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").count(), 1
        )

    def test_expiry_failure_rolls_back_every_write_and_retry_succeeds(self):
        order = self.due(self.buy(multi=True))
        with patch(
            "orders.reservations.StockMovement.objects.bulk_create",
            side_effect=DatabaseError("private SQL/password"),
        ):
            result = self.sweep()
        self.assertFalse(result["passed"])
        self.assertEqual(result["failures"], [{"order_id": order.pk, "code": "database_error"}])
        order.refresh_from_db()
        self.assertEqual(order.status, "PENDING_PAYMENT")
        self.assertIsNone(order.expired_at)
        self.assertEqual(
            [
                Stock.objects.get(offer=o).available_quantity
                for o in [self.offer, self.second_offer]
            ],
            [9, 3],
        )
        self.assertFalse(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").exists()
        )
        self.assertEqual(self.sweep()["expired_order_ids"], [order.pk])

    def test_partial_batch_commits_good_order_without_looping_on_corrupt_oldest(self):
        corrupt = self.due(self.buy())
        valid = self.due(self.buy())
        Order.objects.filter(pk=corrupt.pk).update(total="999.00")
        result = self.sweep(limit=10)
        self.assertEqual(result["attempted_order_ids"], [corrupt.pk, valid.pk])
        self.assertEqual(result["expired_order_ids"], [valid.pk])
        self.assertEqual(
            result["failures"], [{"order_id": corrupt.pk, "code": "integrity_conflict"}]
        )
        self.assertEqual(Order.objects.get(pk=corrupt.pk).status, "PENDING_PAYMENT")
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 9)

    def test_attempt_limit_bounds_failures_and_progress(self):
        orders = [self.due(self.buy()) for _ in range(3)]
        result = self.sweep(limit=2)
        self.assertEqual(result["attempted_order_ids"], [o.pk for o in orders[:2]])
        self.assertEqual(Order.objects.get(pk=orders[2].pk).status, "PENDING_PAYMENT")

    def test_overdue_pending_still_counts_toward_release_headroom(self):
        self.due(self.buy())
        with self.assertRaises(OrderConflict):
            change_stock(
                actor=self.admin,
                offer_id=self.offer.pk,
                movement_type="ADJUSTMENT",
                quantity_delta=MAX_STOCK_QUANTITY - 9,
                reason="Attempt to consume reserved headroom.",
            )
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 9)

    def test_permissions_limits_and_outer_transaction_are_rejected(self):
        for actor in [self.buyer, None]:
            with self.assertRaises(PermissionDenied):
                expire_due_reservations(actor=actor)
        for limit in [0, 1001, True, "1"]:
            with self.assertRaises(ValidationError):
                self.sweep(limit=limit)
        with transaction.atomic(), self.assertRaises(RuntimeError):
            self.sweep()
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.sweep()

    def test_command_target_guard_success_and_role_guard(self):
        order = self.due(self.buy())
        with self.assertRaises(CommandError):
            call_command(
                "expire_reservations",
                expected_database="wrong_database",
                actor_email=self.admin.email,
                stdout=StringIO(),
            )
        out = StringIO()
        with patch("orders.management.commands.expire_reservations.Command.confirm_target"):
            call_command(
                "expire_reservations",
                expected_database=connection.settings_dict["NAME"],
                actor_email=self.admin.email,
                limit=1,
                stdout=out,
            )
        self.assertEqual(json.loads(out.getvalue())["expired_order_ids"], [order.pk])
        # The real test role must be refused even for the correctly named database.
        with self.assertRaises(CommandError):
            call_command(
                "expire_reservations",
                expected_database=connection.settings_dict["NAME"],
                actor_email=self.admin.email,
                stdout=StringIO(),
            )

    def test_command_partial_failure_emits_sanitized_json_and_nonzero(self):
        order = self.due(self.buy())
        Order.objects.filter(pk=order.pk).update(total="999.00")
        out = StringIO()
        with (
            patch("orders.management.commands.expire_reservations.Command.confirm_target"),
            self.assertRaises(CommandError),
        ):
            call_command(
                "expire_reservations",
                expected_database=connection.settings_dict["NAME"],
                actor_email=self.admin.email,
                stdout=out,
            )
        report = json.loads(out.getvalue())
        self.assertEqual(report["failures"][0]["code"], "integrity_conflict")
        self.assertNotIn("shipping", out.getvalue())

    def test_database_rejects_incoherent_deadline_and_expired_states(self):
        order = self.buy()
        invalid = [
            {"reservation_expires_at": order.created_at},
            {"status": "EXPIRED"},
            {"status": "EXPIRED", "expired_at": order.created_at, "reservation_expires_at": None},
            {
                "status": "EXPIRED",
                "expired_at": order.reservation_expires_at - timedelta(microseconds=1),
            },
            {"status": "PAID", "paid_at": order.reservation_expires_at},
            {
                "status": "CANCELLED",
                "cancelled_at": order.reservation_expires_at,
                "expired_at": order.reservation_expires_at,
            },
        ]
        for fields in invalid:
            with (
                self.subTest(fields=fields),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                Order.objects.filter(pk=order.pk).update(**fields)

    def test_expired_order_replay_is_coherent_and_transitions_rejected(self):
        order = self.due(self.buy(key="expiry-one"))
        self.sweep()
        replay = self.buy(key="expiry-one")
        self.assertEqual(
            (replay.pk, replay.status, replay.reservation_expires_at),
            (order.pk, "EXPIRED", order.reservation_expires_at),
        )
        for transition, actor in [
            (cancel_order, self.buyer),
            (approve_simulated_payment, self.admin),
            (ship_order, self.admin),
            (deliver_order, self.admin),
        ]:
            with self.assertRaises(OrderConflict):
                transition(actor=actor, order_id=order.pk)
        response = self.client_for(self.buyer).get("/api/orders/?status=EXPIRED")
        self.assertEqual(response.data["count"], 1)
        self.assertIsNotNone(response.data["results"][0]["expired_at"])
        self.assertEqual(
            self.client_for(self.other).get(f"/api/orders/{order.pk}/").status_code, 404
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ReservationExpiryConcurrencyTests(
    ControlledConcurrencyMixin, ReservationExpiryFixture, TransactionTestCase
):
    def test_expiry_blocks_payment_and_releases_once(self):
        order = self.due(self.buy())

        def pay(*_):
            try:
                approve_simulated_payment(actor=self.admin, order_id=order.pk)
            except OrderConflict as error:
                return error.code

        first, second = self.run_contended(
            lambda *_: self.sweep(),
            pay,
            pause_before=lambda sql: sql.startswith('UPDATE "inventory_stock"'),
            wait_table="orders_order",
        )
        self.assertEqual(first["expired_order_ids"], [order.pk])
        self.assertEqual(second, "invalid_transition")
        self.assertFalse(SimulatedPayment.objects.exists())

    def test_expiry_blocks_cancellation_and_keeps_terminal_identity(self):
        order = self.due(self.buy())

        def cancel(*_):
            try:
                cancel_order(actor=self.buyer, order_id=order.pk)
            except OrderConflict as error:
                return error.code

        first, second = self.run_contended(
            lambda *_: self.sweep(),
            cancel,
            pause_before=lambda sql: sql.startswith('UPDATE "inventory_stock"'),
            wait_table="orders_order",
        )
        self.assertEqual((first["expired_order_ids"], second), ([order.pk], "invalid_transition"))
        self.assertEqual(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").count(), 1
        )

    def test_keyed_replay_waits_for_expiry_and_preserves_snapshots(self):
        order = self.due(self.buy(key="expiry-race"))
        first, second = self.run_contended(
            lambda *_: self.sweep(),
            lambda *_: self.buy(key="expiry-race"),
            pause_before=lambda sql: sql.startswith('UPDATE "inventory_stock"'),
            wait_table="orders_order",
        )
        self.assertEqual(first["expired_order_ids"], [order.pk])
        self.assertEqual(
            (second.pk, second.status, second.idempotency_replayed), (order.pk, "EXPIRED", True)
        )
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)

    def test_payment_rechecks_clock_after_waiting_for_order(self):
        order = self.buy()
        clock = {"at": order.reservation_expires_at - timedelta(microseconds=1)}

        def holder(locked, release):
            with transaction.atomic():
                Order.objects.select_for_update().get(pk=order.pk)
                locked.set()
                if not release.wait(8):
                    raise TimeoutError("Order clock holder was not released.")
                clock["at"] = order.reservation_expires_at

        def pay(*_):
            try:
                approve_simulated_payment(actor=self.admin, order_id=order.pk)
            except OrderConflict as error:
                return error.code

        with patch("orders.lifecycle.database_now", side_effect=lambda: clock["at"]):
            _, result = self.run_contended(holder, pay, wait_table="orders_order")
        self.assertEqual(result, "reservation_expired")
        self.assertFalse(SimulatedPayment.objects.exists())

    def test_expiry_rechecks_administrator_after_catalog_lock_wait(self):
        order = self.due(self.buy())

        def revoke(locked, release):
            with transaction.atomic():
                lock_offer_inventory([self.offer.pk])
                User.objects.filter(pk=self.admin.pk).update(is_active=False)
                locked.set()
                if not release.wait(8):
                    raise TimeoutError("Administrator revocation was not released.")

        _, result = self.run_contended(revoke, lambda *_: self.sweep(), wait_table="catalog_seller")
        self.assertEqual(result["failures"], [{"order_id": order.pk, "code": "permission_denied"}])
        self.assertEqual(Order.objects.get(pk=order.pk).status, "PENDING_PAYMENT")
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 9)

    def run_skipping(self, first_operation, pause_before):
        locked, release = Event(), Event()
        pids = Queue()

        def worker(label, operation):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put((label, cursor.fetchone()[0]))

                def pause(execute, sql, params, many, context):
                    if label == "first" and pause_before(sql):
                        locked.set()
                        if not release.wait(8):
                            raise TimeoutError("SKIP LOCKED holder was not released.")
                    return execute(sql, params, many, context)

                with (
                    connection.execute_wrapper(pause),
                    CaptureQueriesContext(connection) as queries,
                ):
                    result = operation()
                return result, [q["sql"] for q in queries]
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                first = pool.submit(worker, "first", first_operation)
                first_label, first_pid = pids.get(timeout=5)
                self.assertTrue(locked.wait(5))
                second = pool.submit(worker, "second", self.sweep)
                second_label, second_pid = pids.get(timeout=5)
                self.assertEqual((first_label, second_label), ("first", "second"))
                self.assertNotEqual(first_pid, second_pid)
                result, queries = second.result(timeout=5)
                self.assertEqual(result["attempted_order_ids"], [])
                self.assertTrue(any("FOR UPDATE SKIP LOCKED" in sql for sql in queries))
                self.assertFalse(first.done())
                print(
                    "PostgreSQL skip-locked: "
                    + json.dumps(
                        {
                            "scenario": self._testMethodName,
                            "first_backend_pid": first_pid,
                            "second_backend_pid": second_pid,
                            "locked_row_skipped": True,
                        }
                    ),
                    flush=True,
                )
            finally:
                release.set()
            return first.result(timeout=10)[0]

    def test_two_sweep_workers_skip_locked_order_and_release_once(self):
        order = self.due(self.buy())
        result = self.run_skipping(
            self.sweep, lambda sql: sql.startswith('UPDATE "inventory_stock"')
        )
        self.assertEqual(result["expired_order_ids"], [order.pk])
        self.assertEqual(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").count(), 1
        )

    def test_accepted_payment_makes_sweep_skip_and_never_release(self):
        order = self.buy()
        accepted_at = order.reservation_expires_at - timedelta(microseconds=1)
        with (
            patch("orders.lifecycle.database_now", return_value=accepted_at),
            patch("orders.reservations.database_now", return_value=order.reservation_expires_at),
        ):
            result = self.run_skipping(
                lambda: approve_simulated_payment(actor=self.admin, order_id=order.pk),
                lambda sql: sql.startswith('INSERT INTO "orders_simulated_payment"'),
            )
        self.assertEqual(result.order.status, "PAID")
        self.assertFalse(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").exists()
        )

    def test_cancellation_makes_sweep_skip_without_second_release(self):
        order = self.due(self.buy())
        result = self.run_skipping(
            lambda: cancel_order(actor=self.buyer, order_id=order.pk),
            lambda sql: sql.startswith('UPDATE "inventory_stock"'),
        )
        self.assertEqual(result.order.status, "CANCELLED")
        self.assertEqual(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").count(), 1
        )

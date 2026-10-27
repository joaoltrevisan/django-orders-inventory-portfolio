import hashlib
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from catalog.services import save_offer, save_product, save_seller
from inventory.models import Stock, StockMovement
from inventory.services import change_stock
from orders.exceptions import OrderConflict
from orders.lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from orders.models import Order
from orders.services import create_order

from .controlled_concurrency import ControlledConcurrencyMixin
from .operational_fixture import ADDRESS, operational_fixture


class OrderIdempotencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        operational_fixture(cls)

    def payload(self):
        return {
            "items": [
                {"offer_id": self.offer.pk, "quantity": 1},
                {
                    "offer_id": self.second_offer.pk,
                    "quantity": 1,
                },
            ],
            "shipping_address": dict(ADDRESS),
        }

    def buy(self, key="purchase-one", actor=None, payload=None):
        return create_order(
            actor=actor or self.buyer, idempotency_key=key, **(payload or self.payload())
        )

    def authenticated_client(self, actor=None):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION="Bearer "
            + str(RefreshToken.for_user(actor or self.buyer).access_token)
        )
        return client

    def test_canonical_replay_preserves_snapshots_despite_catalog_and_stock_changes(self):
        first = self.buy()
        self.assertFalse(first.idempotency_replayed)
        before = first.updated_at
        save_product(
            actor=self.admin,
            pk=self.product.pk,
            data={"name": "Renamed Fictional Lamp", "is_active": False},
        )
        save_offer(
            actor=self.admin,
            pk=self.offer.pk,
            data={"simulated_price": "50.00", "is_active": False},
        )
        save_seller(actor=self.admin, pk=self.seller.pk, data={"is_active": False})
        change_stock(
            actor=self.admin,
            offer_id=self.offer.pk,
            movement_type="ADJUSTMENT",
            quantity_delta=-9,
            reason="Fictional availability change.",
        )
        equivalent = self.payload()
        equivalent["items"].reverse()
        equivalent["shipping_address"]["recipient"] = "  Fictional Customer  "
        equivalent["shipping_address"]["complement"] = ""
        replay = self.buy(payload=equivalent)
        self.assertTrue(replay.idempotency_replayed)
        self.assertEqual(replay.pk, first.pk)
        self.assertEqual(replay.updated_at, before)
        self.assertEqual(str(replay.total), "32.50")
        self.assertTrue(all(i.product_name == "Simulated Lamp" for i in replay.snapshot_items))
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 0)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 2)
        self.assertEqual(first.idempotency_key_hash, hashlib.sha256(b"purchase-one").hexdigest())

    def test_different_valid_content_conflicts_without_further_writes(self):
        order = self.buy()
        for field in ["quantity", "address"]:
            payload = self.payload()
            if field == "quantity":
                payload["items"][0]["quantity"] = 2
            else:
                payload["shipping_address"]["number"] = "11"
            with self.subTest(field=field), self.assertRaises(OrderConflict) as error:
                self.buy(payload=payload)
            self.assertEqual(error.exception.code, "idempotency_conflict")
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(StockMovement.objects.filter(order=order).count(), 2)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 9)

    def test_keys_are_case_sensitive_and_customer_scoped(self):
        first = self.buy()
        second = self.buy(actor=self.other)
        third = self.buy(key="Purchase-one")
        self.assertEqual(len({first.pk, second.pk, third.pk}), 3)
        self.assertEqual(second.customer_id, self.other.customer.pk)
        self.assertEqual(first.idempotency_key_hash, second.idempotency_key_hash)
        self.assertNotEqual(first.idempotency_key_hash, third.idempotency_key_hash)

    def test_omitted_keys_keep_legacy_behavior_and_null_columns(self):
        orders = [self.buy(key=None), self.buy(key=None)]
        self.assertNotEqual(orders[0].pk, orders[1].pk)
        self.assertTrue(
            all(o.idempotency_key_hash is None and o.request_fingerprint is None for o in orders)
        )

    def test_invalid_keys_and_invalid_bodies_do_not_consume_keys(self):
        for key in ["", " ", " leading", "trailing ", "a,b", "é", "line\n", "x" * 129, True, 12]:
            with self.subTest(key=repr(key)), self.assertRaises(ValidationError):
                self.buy(key=key)
        invalid = self.payload()
        invalid["items"][0]["quantity"] = 0
        with self.assertRaises(ValidationError):
            self.buy(payload=invalid)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(self.buy(key="x" * 128).idempotency_replayed)

    def test_database_enforces_both_null_or_valid_hashes_and_scoped_uniqueness(self):
        first, second = self.buy(key=None), self.buy(key=None)
        changes = [
            {"idempotency_key_hash": "a" * 64},
            {"request_fingerprint": "b" * 64},
            {"idempotency_key_hash": "A" * 64, "request_fingerprint": "b" * 64},
            {"idempotency_key_hash": "a" * 63, "request_fingerprint": "b" * 64},
            {"idempotency_key_hash": "a" * 64, "request_fingerprint": "invalid"},
        ]
        for values in changes:
            with (
                self.subTest(values=values),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                Order.objects.filter(pk=first.pk).update(**values)
        fields = {"idempotency_key_hash": "a" * 64, "request_fingerprint": "b" * 64}
        Order.objects.filter(pk=first.pk).update(**fields)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=second.pk).update(**fields)
        other = self.buy(key=None, actor=self.other)
        self.assertEqual(Order.objects.filter(pk=other.pk).update(**fields), 1)

    def test_database_failure_rolls_back_key_and_all_writes_then_allows_corrected_retry(self):
        with (
            patch(
                "orders.services.StockMovement.objects.bulk_create",
                side_effect=DatabaseError("Injected failure."),
            ),
            self.assertRaises(DatabaseError),
        ):
            self.buy()
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        self.assertFalse(StockMovement.objects.filter(movement_type="RESERVATION").exists())
        payload = self.payload()
        payload["items"][0]["quantity"] = 2
        order = self.buy(payload=payload)
        self.assertFalse(order.idempotency_replayed)
        self.assertEqual(str(order.total), "45.00")

    def test_insufficient_stock_does_not_consume_key_or_partially_reserve(self):
        payload = self.payload()
        payload["items"][1]["quantity"] = 6
        with self.assertRaises(OrderConflict) as error:
            self.buy(payload=payload)
        self.assertEqual(error.exception.code, "insufficient_stock")
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        self.assertFalse(self.buy().idempotency_replayed)

    def test_replay_after_cancellation_keeps_original_release_and_cancelled_state(self):
        order = self.buy()
        cancelled = cancel_order(actor=self.buyer, order_id=order.pk).order
        replay = self.buy()
        self.assertEqual(replay.status, Order.Status.CANCELLED)
        self.assertEqual(replay.cancelled_at, cancelled.cancelled_at)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        self.assertEqual(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").count(), 2
        )
        self.assertEqual(Order.objects.count(), 1)

    def test_replay_captures_current_processing_state_without_processing_again(self):
        order = self.buy()
        for action, status in [
            (approve_simulated_payment, "PAID"),
            (ship_order, "SHIPPED"),
            (deliver_order, "DELIVERED"),
        ]:
            expected = action(actor=self.admin, order_id=order.pk).order
            replay = self.buy()
            self.assertEqual(replay.pk, order.pk)
            self.assertEqual(replay.status, status)
            self.assertEqual(replay.updated_at, expected.updated_at)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 9)
        self.assertEqual(StockMovement.objects.filter(order=order).count(), 2)

    def test_inconsistent_existing_history_is_rejected_without_silent_repair(self):
        order = self.buy()
        StockMovement.objects.filter(order=order, offer=self.offer).update(quantity_delta=-2)
        with self.assertRaises(OrderConflict) as error:
            self.buy()
        self.assertEqual(error.exception.code, "integrity_conflict")
        self.assertEqual(Order.objects.count(), 1)

    def test_http_creation_replay_conflict_and_internal_fields(self):
        client = self.authenticated_client()
        payload = self.payload()
        first = client.post("/api/orders/", payload, format="json", HTTP_IDEMPOTENCY_KEY="http-one")
        second = client.post(
            "/api/orders/", payload, format="json", HTTP_IDEMPOTENCY_KEY="http-one"
        )
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.data, second.data)
        self.assertEqual(first["Idempotency-Replayed"], "false")
        self.assertEqual(second["Idempotency-Replayed"], "true")
        self.assertNotIn("idempotency_key_hash", first.data)
        payload["shipping_address"]["number"] = "11"
        conflict = client.post(
            "/api/orders/", payload, format="json", HTTP_IDEMPOTENCY_KEY="http-one"
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.data["code"], "idempotency_conflict")
        unkeyed = client.post("/api/orders/", self.payload(), format="json")
        self.assertEqual(unkeyed.status_code, 201)
        self.assertNotIn("Idempotency-Replayed", unkeyed)

    def test_http_validation_precedes_conflict_and_blocks_internal_input(self):
        client = self.authenticated_client()
        self.buy(key="http-one")
        for key in ["", "bad key", "x" * 129, "quoted,key"]:
            response = client.post(
                "/api/orders/", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY=key
            )
            self.assertEqual(response.status_code, 400)
        invalid = self.payload()
        invalid["items"][0]["quantity"] = 0
        self.assertEqual(
            client.post(
                "/api/orders/", invalid, format="json", HTTP_IDEMPOTENCY_KEY="http-one"
            ).status_code,
            400,
        )
        self.assertEqual(
            client.post(
                "/api/orders/", {**self.payload(), "request_fingerprint": "x"}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(Order.objects.count(), 1)

    def test_current_permissions_and_customer_isolation_apply_to_http_replays(self):
        first = self.buy(key="http-one")
        response = self.authenticated_client(self.other).post(
            "/api/orders/", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="http-one"
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.data["id"], first.pk)
        client = self.authenticated_client()
        User.objects.filter(pk=self.buyer.pk).update(is_staff=True)
        self.assertEqual(
            client.post(
                "/api/orders/", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="http-one"
            ).status_code,
            403,
        )
        with self.assertRaises(PermissionDenied):
            self.buy(key="http-one")
        User.objects.filter(pk=self.buyer.pk).update(is_active=False)
        self.assertEqual(
            client.post(
                "/api/orders/", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="http-one"
            ).status_code,
            401,
        )

    def test_keyed_http_database_failure_is_sanitized_and_retry_can_create(self):
        client = self.authenticated_client()
        with patch(
            "orders.services.StockMovement.objects.bulk_create",
            side_effect=DatabaseError("private connection details"),
        ):
            response = client.post(
                "/api/orders/", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="http-failure"
            )
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private", str(response.data))
        self.assertFalse(Order.objects.exists())
        self.assertEqual(
            client.post(
                "/api/orders/", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="http-failure"
            ).status_code,
            201,
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class IdempotencyConcurrencyTests(ControlledConcurrencyMixin, TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        operational_fixture(self)

    def buy(self, quantity=1):
        return create_order(
            actor=self.buyer,
            idempotency_key="concurrent-one",
            items=[
                {
                    "offer_id": self.offer.pk,
                    "quantity": quantity,
                }
            ],
            shipping_address=dict(ADDRESS),
        )

    def capture(self, quantity=1):
        def execute(*_):
            try:
                order = self.buy(quantity)
                return "ok", order.pk, order.idempotency_replayed, order.status
            except OrderConflict as error:
                return "conflict", error.code
            except PermissionDenied:
                return "denied", None

        return execute

    def test_same_key_waits_before_first_row_exists_and_reserves_last_unit_once(self):
        change_stock(
            actor=self.admin,
            offer_id=self.offer.pk,
            movement_type="ADJUSTMENT",
            quantity_delta=-9,
            reason="Controlled last-unit scenario.",
        )
        first, second = self.run_contended(
            self.capture(),
            self.capture(),
            pause_before=lambda sql: sql.startswith('INSERT INTO "orders_order"'),
            wait_query_fragment="pg_advisory_xact_lock",
        )
        self.assertEqual(first[:3], ("ok", second[1], False))
        self.assertEqual(second[0::2], ("ok", True))
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 0)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 1)

    def test_same_key_different_valid_payload_waits_then_conflicts(self):
        first, second = self.run_contended(
            self.capture(),
            self.capture(2),
            pause_before=lambda sql: sql.startswith('INSERT INTO "orders_order"'),
            wait_query_fragment="pg_advisory_xact_lock",
        )
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "idempotency_conflict"))
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 9)

    def test_rollback_after_writes_releases_key_to_waiting_creator(self):
        def failing(locked, release):
            try:
                with transaction.atomic():
                    self.buy()
                    locked.set()
                    if not release.wait(8):
                        raise TimeoutError("The test did not release rollback.")
                    raise DatabaseError("Injected rollback after order writes.")
            except DatabaseError:
                return "rolled_back", None

        first, second = self.run_contended(
            failing, self.capture(), wait_query_fragment="pg_advisory_xact_lock"
        )
        self.assertEqual(first[0], "rolled_back")
        self.assertEqual(second[0], "ok")
        self.assertFalse(second[2])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 9)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 1)

    def test_replay_waits_for_cancellation_and_returns_coherent_cancelled_state(self):
        order = self.buy()

        def cancel(*_):
            return cancel_order(actor=self.buyer, order_id=order.pk).order.status

        first, second = self.run_contended(
            cancel,
            self.capture(),
            pause_before=lambda sql: sql.startswith('UPDATE "orders_order"'),
            wait_table="orders_order",
        )
        self.assertEqual(first, "CANCELLED")
        self.assertEqual(second, ("ok", order.pk, True, "CANCELLED"))
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        self.assertEqual(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").count(), 1
        )

    def test_customer_revoked_during_key_wait_cannot_replay(self):
        def revoke(locked, release):
            with transaction.atomic():
                order = self.buy()
                User.objects.filter(pk=self.buyer.pk).update(is_active=False)
                locked.set()
                if not release.wait(8):
                    raise TimeoutError("The test did not release revocation.")
            return order.pk

        first, second = self.run_contended(
            revoke, self.capture(), wait_query_fragment="pg_advisory_xact_lock"
        )
        self.assertGreater(first, 0)
        self.assertEqual(second, ("denied", None))
        self.assertEqual(Order.objects.count(), 1)

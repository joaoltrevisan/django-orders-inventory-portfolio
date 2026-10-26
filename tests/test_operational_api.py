from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from inventory.models import Stock, StockMovement
from orders.models import Order
from orders.services import create_order

from .operational_fixture import ADDRESS, operational_fixture


class OperationalAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        operational_fixture(cls)

    def setUp(self):
        self.client = APIClient()

    def authenticate(self, actor):
        token = RefreshToken.for_user(actor).access_token
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + str(token))

    def payload(self):
        return {
            "items": [
                {"offer_id": self.offer.pk, "quantity": 2},
                {"offer_id": self.second_offer.pk, "quantity": 1},
            ],
            "shipping_address": dict(ADDRESS),
        }

    def order(self, actor=None):
        return create_order(actor=actor or self.buyer, **self.payload())

    def test_customer_creation_and_read_are_self_scoped_with_server_snapshots(self):
        self.authenticate(self.buyer)
        response = self.client.post("/api/orders/", self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total"], "45.00")
        self.assertEqual(response.data["customer_id"], self.buyer.customer.pk)
        self.assertEqual(response.data["data_origin"], "SIMULATED_API")
        self.assertEqual(response.data["payment_mode"], "SIMULATED_NO_REAL_CHARGE")
        self.assertEqual(len(response.data["items"]), 2)
        self.assertEqual(response["Cache-Control"], "no-store")
        other = self.order(actor=self.other)
        listing = self.client.get("/api/orders/")
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(self.client.get(f"/api/orders/{other.pk}/").status_code, 404)
        self.assertEqual(
            self.client.post(f"/api/orders/{other.pk}/cancel/", {}, format="json").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"/api/orders/?customer_id={self.other.customer.pk}").status_code, 403
        )
        detail = self.client.get(f"/api/orders/{response.data['id']}/")
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertIsNone(detail.data["simulated_payment"])
        self.assertIsNone(detail.data["shipment"])

    def test_protected_order_fields_and_bad_quantities_are_rejected_without_writes(self):
        self.authenticate(self.buyer)
        for extra in [
            {"total": "0.01"},
            {"customer_id": self.other.customer.pk},
            {"status": "PAID"},
            {"currency": "USD"},
            {"created_at": "2020-01-01"},
        ]:
            response = self.client.post("/api/orders/", {**self.payload(), **extra}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
        for quantity in [True, "1", 1.5, 0, -1, 10000]:
            data = {**self.payload(), "items": [{"offer_id": self.offer.pk, "quantity": quantity}]}
            self.assertEqual(self.client.post("/api/orders/", data, format="json").status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_admin_processing_permissions_and_complete_action_responses(self):
        order = self.order()
        self.authenticate(self.buyer)
        for action in ["simulated-payment", "ship", "deliver"]:
            self.assertEqual(
                self.client.post(
                    f"/api/orders/{order.pk}/{action}/", {}, format="json"
                ).status_code,
                403,
            )
        self.authenticate(self.admin)
        self.assertEqual(
            self.client.post("/api/orders/", self.payload(), format="json").status_code, 403
        )
        self.assertEqual(self.client.get("/api/orders/").data["count"], 1)
        self.assertEqual(
            self.client.get(f"/api/orders/?customer_id={self.buyer.customer.pk}").data["count"], 1
        )
        self.assertEqual(
            self.client.post(f"/api/orders/{order.pk}/deliver/", {}, format="json").status_code, 409
        )
        paid = self.client.post(f"/api/orders/{order.pk}/simulated-payment/", {}, format="json")
        self.assertEqual(paid.status_code, 200, paid.data)
        self.assertTrue(paid.data["simulated_payment"]["is_simulated"])
        self.assertEqual(
            paid.data["simulated_payment"]["payment_record_kind"],
            "SIMULATED_APPROVAL_NO_REAL_CHARGE",
        )
        self.assertEqual(paid.data["order"]["status"], "PAID")
        self.assertEqual(
            self.client.post(f"/api/orders/{order.pk}/cancel/", {}, format="json").status_code, 409
        )
        shipment = self.client.post(
            f"/api/orders/{order.pk}/ship/", {"tracking_code": "SIMULATED-HTTP-1"}, format="json"
        )
        self.assertEqual(shipment.status_code, 200, shipment.data)
        delivered = self.client.post(f"/api/orders/{order.pk}/deliver/", {}, format="json")
        self.assertEqual(delivered.status_code, 200, delivered.data)
        self.assertEqual(delivered.data["order"]["status"], "DELIVERED")
        self.assertEqual(
            self.client.patch(
                f"/api/orders/{order.pk}/", {"status": "PENDING_PAYMENT"}, format="json"
            ).status_code,
            405,
        )
        self.assertEqual(self.client.delete(f"/api/orders/{order.pk}/").status_code, 405)

    def test_cancellation_repeated_over_http_changes_stock_once(self):
        order = self.order()
        self.authenticate(self.buyer)
        path = f"/api/orders/{order.pk}/cancel/"
        first = self.client.post(path, {}, format="json")
        second = self.client.post(path, {}, format="json")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data, second.data)
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)
        self.assertEqual(
            StockMovement.objects.filter(order=order, movement_type="RELEASE").count(), 2
        )

    def test_inventory_admin_only_validated_auditable_and_read_only_history(self):
        self.authenticate(self.buyer)
        self.assertEqual(self.client.get("/api/inventory/").status_code, 403)
        self.assertEqual(self.client.get("/api/inventory/movements/").status_code, 403)
        self.authenticate(self.admin)
        self.assertEqual(self.client.get("/api/inventory/").data["count"], 2)
        response = self.client.post(
            f"/api/inventory/{self.offer.pk}/changes/",
            {
                "movement_type": "ENTRY",
                "quantity_delta": 4,
                "reason": "Fictional administrative entry.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["stock"]["available_quantity"], 14)
        self.assertEqual(response.data["movement"]["performed_by_id"], self.admin.pk)
        for data in [
            {"available_quantity": 999},
            {"movement_type": "ENTRY", "quantity_delta": True, "reason": "Example"},
            {"movement_type": "ENTRY", "quantity_delta": 1, "reason": " "},
            {
                "movement_type": "ENTRY",
                "quantity_delta": 1,
                "reason": "Example",
                "performed_by_id": self.buyer.pk,
            },
        ]:
            self.assertEqual(
                self.client.post(
                    f"/api/inventory/{self.offer.pk}/changes/", data, format="json"
                ).status_code,
                400,
            )
        movements = self.client.get(f"/api/inventory/movements/?offer_id={self.offer.pk}")
        self.assertEqual(movements.status_code, 200)
        self.assertEqual(movements.data["count"], 2)
        self.assertEqual(
            self.client.get("/api/inventory/movements/?offer_id=invalid").status_code, 400
        )
        self.assertEqual(
            self.client.patch(
                f"/api/inventory/{self.offer.pk}/", {"available_quantity": 0}, format="json"
            ).status_code,
            405,
        )
        self.assertEqual(
            self.client.post("/api/inventory/movements/", {}, format="json").status_code, 405
        )

    def test_database_failure_returns_sanitized_response_after_full_rollback(self):
        self.authenticate(self.buyer)
        with patch(
            "orders.services.StockMovement.objects.bulk_create",
            side_effect=DatabaseError("private SQL credentials source content"),
        ):
            response = self.client.post("/api/orders/", self.payload(), format="json")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["code"], "database_error")
        self.assertNotIn("private", str(response.data))
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 10)

    def test_missing_or_invalid_credentials_and_action_payloads(self):
        self.assertEqual(self.client.get("/api/orders/").status_code, 401)
        self.authenticate(self.buyer)
        order = self.order()
        self.assertEqual(
            self.client.post(
                f"/api/orders/{order.pk}/cancel/", {"quantity": 999}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(self.client.get("/api/orders/?status=invalid").status_code, 400)
        self.assertEqual(self.client.get("/api/orders/0/").status_code, 404)

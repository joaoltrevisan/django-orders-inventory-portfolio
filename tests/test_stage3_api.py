from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Customer, User
from accounts.services import manage_customer, update_profile
from catalog.models import Offer, Product, Seller
from catalog.services import save_product
from inventory.models import Stock

from .factories import historical_records

PASSWORD = "Fictional-Access-7392!"


class AccountFixture:
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin@example.com", PASSWORD, name="Demo Admin")
        cls.buyer = User.objects.create_user("buyer@example.com", PASSWORD, name="Demo Buyer")
        cls.other = User.objects.create_user("other@example.com", PASSWORD, name="Other Buyer")
        cls.customer = Customer.objects.create(user=cls.buyer)
        Customer.objects.create(user=cls.other)

    def setUp(self):
        self.client = APIClient()

    def tokens(self, email="buyer@example.com"):
        response = self.client.post(
            "/api/auth/login/", {"email": email, "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def authenticate(self, email="buyer@example.com"):
        tokens = self.tokens(email)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + tokens["access"])
        return tokens


class AccountAPITests(AccountFixture, TestCase):
    def test_services_recheck_inactive_or_revoked_callers_and_admin_can_reactivate(self):
        User.objects.filter(pk=self.buyer.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            update_profile(user=self.buyer, name="Forbidden change")
        managed = manage_customer(
            actor=self.admin, customer=self.customer, name="Managed inactive buyer", is_active=True
        )
        self.assertTrue(managed.is_active)
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        with self.assertRaises(PermissionDenied):
            manage_customer(actor=self.admin, customer=self.customer, name="Forbidden")
        with self.assertRaises(PermissionDenied):
            save_product(actor=self.admin, data={"sku": "NOPE", "name": "Forbidden"})

    def test_registration_is_atomic_hashed_and_never_grants_staff(self):
        data = {"email": " New@EXAMPLE.COM ", "name": "Fictional Customer", "password": PASSWORD}
        response = self.client.post("/api/auth/register/", data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="new@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(Customer.objects.filter(user=user).exists())
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(response.data["data_origin"], "SIMULATED_API")
        self.assertNotIn("password", response.data)
        for extra in [{"is_staff": True}, {"customer_unique_id": "a" * 32}, {"id": 99}]:
            response = self.client.post("/api/auth/register/", {**data, **extra}, format="json")
            self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(email="new@example.com").count(), 1)

    def test_registration_validation_and_duplicate_email(self):
        for changes in [
            {"password": "12345678"},
            {"email": "bad"},
            {"name": " "},
            {"email": "BUYER@example.com"},
        ]:
            response = self.client.post(
                "/api/auth/register/",
                {
                    "email": "fresh@example.com",
                    "name": "Fictional Name",
                    "password": PASSWORD,
                    **changes,
                },
                format="json",
            )
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(User.objects.filter(email="fresh@example.com").exists())

    def test_case_insensitive_login_profile_and_refresh(self):
        tokens = self.authenticate("BUYER@EXAMPLE.COM")
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.data["id"], self.buyer.pk)
        self.assertEqual(response["Cache-Control"], "no-store")
        refresh = self.client.post(
            "/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(refresh.status_code, 200)
        self.assertEqual(set(refresh.data), {"access"})

    def test_wrong_password_and_unauthenticated_requests(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        response = self.client.post(
            "/api/auth/login/",
            {"email": "buyer@example.com", "password": "incorrect"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("No active account", str(response.data))

    def test_profile_is_self_only_and_identity_privileges_are_protected(self):
        self.authenticate()
        response = self.client.patch(
            "/api/auth/me/", {"name": "Updated Buyer", "phone": "555-0100"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        for field, value in [
            ("email", "other@example.com"),
            ("id", self.other.pk),
            ("is_staff", True),
            ("is_active", False),
        ]:
            self.assertEqual(
                self.client.patch("/api/auth/me/", {field: value}, format="json").status_code, 400
            )
        self.other.refresh_from_db()
        self.assertEqual(self.other.name, "Other Buyer")
        self.assertEqual(self.client.get("/api/customers/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/customers/{self.customer.pk}/").status_code, 403)

    def test_admin_customer_management_uses_profile_keys_and_paginated_list(self):
        self.authenticate("admin@example.com")
        response = self.client.get("/api/customers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        row = response.data["results"][0]
        detail = self.client.get(f"/api/customers/{row['id']}/")
        self.assertEqual(detail.data["user_id"], row["user_id"])
        response = self.client.patch(
            f"/api/customers/{self.customer.pk}/",
            {"name": "Managed Buyer", "is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["is_active"])
        self.assertEqual(self.client.delete(f"/api/customers/{self.customer.pk}/").status_code, 405)

    def test_current_account_state_revokes_both_access_and_refresh(self):
        for action in ["deactivate", "password", "delete"]:
            user = User.objects.create_user(f"{action}@example.com", PASSWORD, name="Token Fixture")
            token = RefreshToken.for_user(user)
            access = str(token.access_token)
            refresh = str(token)
            if action == "deactivate":
                user.is_active = False
                user.save(update_fields=["is_active"])
            elif action == "password":
                user.set_password("Changed-Fictional-681!")
                user.save(update_fields=["password"])
            else:
                user.delete()
            self.client.credentials(HTTP_AUTHORIZATION="Bearer " + access)
            self.assertEqual(self.client.get("/api/auth/me/").status_code, 401, action)
            self.client.credentials()
            response = self.client.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
            self.assertEqual(response.status_code, 401, (action, response.data))

    def test_expired_wrong_type_and_malformed_identity_tokens_are_safe(self):
        for user_id in [None, 0, {}, "9" * 30, "-1", "1.0"]:
            token = RefreshToken.for_user(self.buyer)
            token["user_id"] = user_id
            self.client.credentials(HTTP_AUTHORIZATION="Bearer " + str(token.access_token))
            self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
            self.client.credentials()
            self.assertEqual(
                self.client.post(
                    "/api/auth/refresh/", {"refresh": str(token)}, format="json"
                ).status_code,
                401,
            )
        token = RefreshToken.for_user(self.buyer)
        for value in [str(token.access_token), "invalid.jwt.value"]:
            self.assertEqual(
                self.client.post(
                    "/api/auth/refresh/", {"refresh": value}, format="json"
                ).status_code,
                401,
            )
        token.set_exp(lifetime=-timedelta(seconds=1))
        self.assertEqual(
            self.client.post(
                "/api/auth/refresh/", {"refresh": str(token)}, format="json"
            ).status_code,
            401,
        )
        access = RefreshToken.for_user(self.buyer).access_token
        access.set_exp(lifetime=-timedelta(seconds=1))
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + str(access))
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_admin_privilege_changes_apply_to_existing_access_tokens(self):
        self.authenticate("admin@example.com")
        self.admin.is_staff = False
        self.admin.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get("/api/customers/").status_code, 403)


class CatalogAPITests(AccountFixture, TestCase):
    # Reuse only the authenticated account fixture; account tests remain in their own class.
    def test_catalog_permissions_offer_initialization_and_deactivation(self):
        self.authenticate()
        self.assertEqual(
            self.client.post(
                "/api/products/", {"sku": "SKU-1", "name": "Demo"}, format="json"
            ).status_code,
            403,
        )
        self.authenticate("admin@example.com")
        product = self.client.post(
            "/api/products/", {"sku": "SKU-1", "name": "Simulated Product"}, format="json"
        )
        self.assertEqual(product.status_code, 201, product.data)
        seller = self.client.post("/api/sellers/", {"label": "Simulated Seller"}, format="json")
        self.assertEqual(seller.status_code, 201)
        data = {
            "product_id": product.data["id"],
            "seller_id": seller.data["id"],
            "simulated_price": "15.25",
        }
        offer = self.client.post("/api/offers/", data, format="json")
        self.assertEqual(offer.status_code, 201, offer.data)
        self.assertEqual(offer.data["available_quantity"], 0)
        self.assertEqual(Stock.objects.get(offer_id=offer.data["id"]).available_quantity, 0)
        self.assertEqual(self.client.post("/api/offers/", data, format="json").status_code, 400)
        self.assertEqual(
            self.client.patch(
                f"/api/offers/{offer.data['id']}/", {"seller_id": 999}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/products/{product.data['id']}/", {"sku": "REASSIGNED"}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.delete(f"/api/products/{product.data['id']}/").status_code, 405
        )
        self.client.patch(f"/api/sellers/{seller.data['id']}/", {"is_active": False}, format="json")
        self.authenticate()
        self.assertEqual(self.client.get("/api/offers/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/offers/{offer.data['id']}/").status_code, 404)

    def test_catalog_rejects_invalid_and_protected_input(self):
        self.authenticate("admin@example.com")
        product = Product.objects.create(sku="DEMO-1", name="Simulated Product")
        seller = Seller.objects.create(label="Simulated Seller")
        data = {"product_id": product.pk, "seller_id": seller.pk, "simulated_price": "5.00"}
        for changes in [
            {"simulated_price": "0.00"},
            {"simulated_price": "NaN"},
            {"simulated_price": "1.001"},
            {"simulated_price": 5.0},
            {"seller_id": True},
            {"available_quantity": 10},
            {"data_origin": "OLIST_HISTORICAL"},
        ]:
            response = self.client.post("/api/offers/", {**data, **changes}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Offer.objects.count(), 0)
        self.assertEqual(Stock.objects.count(), 0)


class HistoricalAPITests(AccountFixture, TestCase):
    def test_history_is_admin_only_completed_paginated_and_read_only(self):
        snapshot, customer, _, _, order = historical_records()
        self.authenticate()
        self.assertEqual(self.client.get("/api/olist/orders/").status_code, 403)
        self.assertEqual(
            self.client.get(f"/api/olist/orders/{order.source_order_id}/").status_code, 403
        )
        self.authenticate("admin@example.com")
        self.assertEqual(self.client.get("/api/olist/orders/").data["count"], 0)
        snapshot.publication_status = "COMPLETE"
        snapshot.save(update_fields=["publication_status"])
        with timezone.override("America/Sao_Paulo"):
            response = self.client.get(f"/api/olist/orders/{order.source_order_id}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["purchased_at_source"], "2017-03-01 00:15:00")
        self.assertEqual(response.data["customer"], customer.source_customer_id)
        self.assertEqual(response.data["customer_unique_id"], customer.customer_unique_id)
        self.assertEqual(response.data["data_origin"], "OLIST_HISTORICAL")
        for route in [
            "customers",
            "categories",
            "products",
            "sellers",
            "orders",
            "items",
            "payments",
        ]:
            listing = self.client.get(f"/api/olist/{route}/")
            self.assertEqual(listing.status_code, 200, listing.data)
            self.assertIn("results", listing.data)
            self.assertEqual(
                self.client.post(f"/api/olist/{route}/", {}, format="json").status_code, 405
            )
        self.assertEqual(
            self.client.patch(
                f"/api/olist/orders/{order.source_order_id}/",
                {"source_status": "canceled"},
                format="json",
            ).status_code,
            405,
        )
        self.assertEqual(self.client.get("/api/olist/items/?order_id=invalid").status_code, 400)

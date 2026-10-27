"""Small fictional operational dataset built through actual business services."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from accounts.models import Customer, User
from catalog.services import save_offer, save_product, save_seller
from inventory.services import change_stock

from .lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from .services import create_order

DEMO_LOCK = (73019, 6)
ADDRESS = {
    "recipient": "Fictional Customer",
    "street": "Example Street",
    "number": "10",
    "district": "Example District",
    "city": "Example City",
    "state": "SP",
    "postal_code": "00000000",
}


def seed_demo(*, expected_database, password):
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        database = cursor.fetchone()[0]
    if database != expected_database or not (
        database == "olist_demo" or database.startswith("test_")
    ):
        raise ValueError(
            "Fictional seeding requires the explicitly confirmed isolated demo database."
        )
    if not isinstance(password, str) or len(password) < 24:
        raise ValidationError("Provide a private demo password of at least 24 characters.")
    validate_password(password)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(%s,%s)", DEMO_LOCK)
        if not cursor.fetchone()[0]:
            raise ValueError("Another demo seed is already running.")
        # Allow only migration/content-type/permission metadata, not any domain data.
        for table in connection.introspection.table_names():
            if table != "auth_permission" and table.startswith(
                ("olist_", "accounts_", "catalog_", "inventory_", "orders_", "auth_")
            ):
                cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {connection.ops.quote_name(table)})")
                if cursor.fetchone()[0]:
                    raise ValueError(
                        "Demo seeding refuses a nonempty historical or operational domain."
                    )
        admin = User.objects.create_superuser(
            "admin@example.com", password, name="Fictional Administrator"
        )
        customers = []
        for number in range(1, 4):
            user = User.objects.create_user(
                f"customer{number}@example.com", password, name=f"Fictional Customer {number}"
            )
            Customer.objects.create(user=user)
            customers.append(user)
        product = save_product(actor=admin, data={"sku": "DEMO-LAMP", "name": "Simulated Lamp"})
        desk = save_product(actor=admin, data={"sku": "DEMO-DESK", "name": "Simulated Desk"})
        sellers = [
            save_seller(actor=admin, data={"label": f"Simulated Seller {number}"})
            for number in [1, 2]
        ]
        offers = [
            save_offer(
                actor=admin,
                data={
                    "seller_id": sellers[0].pk,
                    "product_id": product.pk,
                    "simulated_price": "25.90",
                },
            ),
            save_offer(
                actor=admin,
                data={
                    "seller_id": sellers[1].pk,
                    "product_id": product.pk,
                    "simulated_price": "30.00",
                },
            ),
            save_offer(
                actor=admin,
                data={
                    "seller_id": sellers[0].pk,
                    "product_id": desk.pk,
                    "simulated_price": "100.00",
                },
            ),
        ]
        for offer in offers:
            change_stock(
                actor=admin,
                offer_id=offer.pk,
                movement_type="ENTRY",
                quantity_delta=20,
                reason="Initial fictional demo supply.",
            )
        orders = []
        for number in range(5):
            items = [{"offer_id": offers[number % 3].pk, "quantity": 1}]
            if number == 0:
                items.append({"offer_id": offers[1].pk, "quantity": 2})
            order = create_order(
                actor=customers[number % 2], items=items, shipping_address=dict(ADDRESS)
            )
            if number == 1:
                cancel_order(actor=customers[1], order_id=order.pk)
            elif number in [2, 3, 4]:
                approve_simulated_payment(actor=admin, order_id=order.pk)
                if number in [3, 4]:
                    ship_order(
                        actor=admin, order_id=order.pk, tracking_code=f"SIMULATED-DEMO-{number}"
                    )
                if number == 4:
                    deliver_order(actor=admin, order_id=order.pk)
            order.refresh_from_db()
            orders.append({"id": order.pk, "status": order.status, "total": str(order.total)})
    return {
        "data_origin": "SIMULATED_API",
        "database": database,
        "users": 4,
        "customers": 3,
        "products": 2,
        "sellers": 2,
        "offers": 3,
        "orders": orders,
        "note": (
            "No historical source records. Accounts, inventory, prices, payments and "
            "deliveries are simulated. Password salts, UUIDs and times differ across fresh runs."
        ),
    }

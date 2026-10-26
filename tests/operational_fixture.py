"""Fictional operational fixtures, intentionally unrelated to source customer/seller IDs."""

from accounts.models import Customer, User
from catalog.models import Product, Seller
from catalog.services import save_offer
from inventory.services import change_stock

PASSWORD = "Operational-Fixture-729!"
ADDRESS = {
    "recipient": "Fictional Customer",
    "street": "Example Street",
    "number": "10",
    "district": "Example District",
    "city": "Example City",
    "state": "SP",
    "postal_code": "00000000",
}


def operational_fixture(target):
    target.admin = User.objects.create_superuser(
        "operations@example.com", PASSWORD, name="Fictional Administrator"
    )
    target.buyer = User.objects.create_user("buyer@example.com", PASSWORD, name="Fictional Buyer")
    target.other = User.objects.create_user(
        "other@example.com", PASSWORD, name="Other Fictional Buyer"
    )
    Customer.objects.create(user=target.buyer)
    Customer.objects.create(user=target.other)
    target.product = Product.objects.create(sku="OP-001", name="Simulated Lamp")
    target.seller = Seller.objects.create(label="Simulated Seller One")
    target.second_seller = Seller.objects.create(label="Simulated Seller Two")
    target.offer = save_offer(
        actor=target.admin,
        data={
            "seller_id": target.seller.pk,
            "product_id": target.product.pk,
            "simulated_price": "12.50",
        },
    )
    target.second_offer = save_offer(
        actor=target.admin,
        data={
            "seller_id": target.second_seller.pk,
            "product_id": target.product.pk,
            "simulated_price": "20.00",
        },
    )
    change_stock(
        actor=target.admin,
        offer_id=target.offer.pk,
        movement_type="ENTRY",
        quantity_delta=10,
        reason="Initial fictional supply.",
    )
    change_stock(
        actor=target.admin,
        offer_id=target.second_offer.pk,
        movement_type="ENTRY",
        quantity_delta=5,
        reason="Initial fictional supply.",
    )

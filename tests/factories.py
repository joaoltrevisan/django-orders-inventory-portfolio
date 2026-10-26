"""Small fictional records for model checks; never presented as Olist observations."""

from datetime import UTC, datetime

from accounts.models import Customer, User
from catalog.models import Offer, Product, Seller
from olist.models import (
    DatasetSnapshot,
    HistoricalCustomer,
    HistoricalOrder,
    HistoricalProduct,
    HistoricalSeller,
)
from orders.models import Order


def historical_records():
    snapshot = DatasetSnapshot.objects.create(
        dataset_ref="test/fictional-fixture",
        source_url="https://example.com/fixture",
        reported_version="test",
        archive_sha256="0" * 64,
        member_manifest={},
        mapping_version="test-1",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    customer = HistoricalCustomer.objects.create(
        snapshot=snapshot,
        source_customer_id="a" * 32,
        customer_unique_id="b" * 32,
        zip_code_prefix="00123",
        city="Fictional City",
        state="SP",
    )
    product = HistoricalProduct.objects.create(snapshot=snapshot, source_product_id="c" * 32)
    seller = HistoricalSeller.objects.create(
        snapshot=snapshot,
        source_seller_id="d" * 32,
        zip_code_prefix="00001",
        city="Fictional Seller City",
        state="SP",
    )
    order = HistoricalOrder.objects.create(
        snapshot=snapshot,
        source_order_id="e" * 32,
        customer=customer,
        source_status="delivered",
        purchased_at_raw="2017-03-01 00:15:00",
        purchased_at_source=datetime(2017, 3, 1, 0, 15),
    )
    return snapshot, customer, product, seller, order


def simulated_records():
    user = User.objects.create_user(
        email="customer@example.com", password="test-fixture-password", name="Fictional Buyer"
    )
    customer = Customer.objects.create(user=user)
    product = Product.objects.create(sku="DEMO-001", name="Simulated product")
    seller = Seller.objects.create(label="Simulated seller")
    offer = Offer.objects.create(seller=seller, product=product, simulated_price="12.50")
    order = Order.objects.create(
        customer=customer,
        total="25.00",
        shipping_recipient="Fictional Buyer",
        shipping_street="Example Street",
        shipping_number="10",
        shipping_district="Example",
        shipping_city="Example City",
        shipping_state="SP",
        shipping_postal_code="00000000",
    )
    return user, product, seller, offer, order

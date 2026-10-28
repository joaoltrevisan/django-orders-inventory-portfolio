"""Atomic multi-seller reservations adapted from the existing order service."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.permissions import require_customer
from catalog.locking import lock_offer_inventory
from common.limits import MAX_ORDER_TOTAL
from inventory.models import StockMovement
from inventory.services import inspect_stock

from .exceptions import OrderConflict
from .idempotency import key_hash, lock_creation_key, request_fingerprint
from .integrity import inspect_order_history
from .models import Order, OrderItem
from .reservations import RESERVATION_LIFETIME
from .validation import validate_order_input


def create_order(*, actor, items, shipping_address, idempotency_key=None):
    customer = require_customer(actor)
    items, address = validate_order_input(items=items, shipping_address=shipping_address)
    digest = key_hash(idempotency_key)
    fingerprint = request_fingerprint(items, address) if digest is not None else None
    quantities = {line["offer_id"]: line["quantity"] for line in items}
    with transaction.atomic():
        if digest is not None:
            lock_creation_key(customer.pk, digest)
            customer = require_customer(actor)
            previous = (
                Order.objects.select_for_update()
                .filter(customer=customer, idempotency_key_hash=digest)
                .first()
            )
            if previous is not None:
                if previous.request_fingerprint != fingerprint:
                    raise OrderConflict(
                        "idempotency_conflict",
                        "This key was already used for different order content.",
                    )
                inspect_order_history(previous)
                previous.idempotency_replayed = True
                return previous
        offers, sellers, products, stocks = lock_offer_inventory(quantities)
        inspect_stock(stocks)
        for offer in offers:
            if (
                not offer.is_active
                or not sellers[offer.seller_id].is_active
                or not products[offer.product_id].is_active
            ):
                raise OrderConflict("offer_inactive", "A seller, product or offer is inactive.")
            if stocks[offer.pk].available_quantity < quantities[offer.pk]:
                raise OrderConflict(
                    "insufficient_stock", f"Insufficient stock for offer {offer.pk}."
                )
        total = sum(
            (offer.simulated_price * quantities[offer.pk] for offer in offers), Decimal("0.00")
        )
        if not total.is_finite() or not Decimal("0.00") < total <= MAX_ORDER_TOTAL:
            raise ValidationError(
                {"items": ["The calculated total is outside the supported range."]}
            )
        order = Order.objects.create(
            customer=customer,
            total=total,
            idempotency_key_hash=digest,
            request_fingerprint=fingerprint,
            **{"shipping_" + key: value for key, value in address.items()},
        )
        order.reservation_expires_at = order.created_at + RESERVATION_LIFETIME
        order.save(update_fields=["reservation_expires_at"])
        lines = OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    offer=offer,
                    quantity=quantities[offer.pk],
                    unit_price=offer.simulated_price,
                    product_sku=products[offer.product_id].sku,
                    product_name=products[offer.product_id].name,
                    seller_label=sellers[offer.seller_id].label,
                )
                for offer in offers
            ]
        )
        for offer_id, stock in stocks.items():
            stock.available_quantity -= quantities[offer_id]
            stock.save(update_fields=["available_quantity", "updated_at"])
        StockMovement.objects.bulk_create(
            [
                StockMovement(
                    offer=offer,
                    order=order,
                    performed_by=actor,
                    movement_type="RESERVATION",
                    quantity_delta=-quantities[offer.pk],
                    reason="Reservation on simulated order creation.",
                )
                for offer in offers
            ]
        )
        order.snapshot_items = lines
        order.idempotency_replayed = False
        return order

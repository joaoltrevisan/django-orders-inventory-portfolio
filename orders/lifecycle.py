"""Locked, auditable simulated order transitions; never real payment processing."""

from dataclasses import dataclass

from django.db import transaction
from django.http import Http404
from django.utils import timezone

from accounts.permissions import require_administrator
from catalog.locking import lock_offer_inventory
from common.limits import MAX_STOCK_QUANTITY
from common.validation import clean_text, validate_id
from inventory.models import StockMovement
from inventory.services import inspect_stock

from .exceptions import OrderConflict
from .integrity import inspect_order_history
from .models import Order, Shipment, SimulatedPayment
from .selectors import orders_visible_to


@dataclass(frozen=True)
class OrderTransitionResult:
    order: Order
    simulated_payment: SimulatedPayment | None
    shipment: Shipment | None


def locked_order(actor, order_id):
    validate_id(order_id)
    try:
        # Scope through a subquery, so FOR UPDATE locks only the order table.
        return Order.objects.select_for_update().get(
            pk=order_id, id__in=orders_visible_to(actor).values("id")
        )
    except Order.DoesNotExist as error:
        raise Http404("Order not found.") from error


def cancel_order(*, actor, order_id):
    with transaction.atomic():
        order = locked_order(actor, order_id)
        history = inspect_order_history(order)
        if order.status not in {Order.Status.PENDING_PAYMENT, Order.Status.CANCELLED}:
            raise OrderConflict("invalid_transition", "Only a pending order can be cancelled.")
        quantities = {item.offer_id: item.quantity for item in history.items}
        _, _, _, stocks = lock_offer_inventory(quantities)
        inspect_stock(stocks)
        if order.status == Order.Status.CANCELLED:
            return OrderTransitionResult(order, None, None)
        if any(
            stock.available_quantity + quantities[key] > MAX_STOCK_QUANTITY
            for key, stock in stocks.items()
        ):
            raise OrderConflict("stock_limit_exceeded", "Cancellation would exceed stock capacity.")
        at = timezone.now()
        for key, stock in stocks.items():
            stock.available_quantity += quantities[key]
            stock.save(update_fields=["available_quantity", "updated_at"])
        StockMovement.objects.bulk_create(
            [
                StockMovement(
                    order=order,
                    offer_id=key,
                    performed_by=actor,
                    movement_type="RELEASE",
                    quantity_delta=quantity,
                    reason="Release on simulated order cancellation.",
                )
                for key, quantity in sorted(quantities.items())
            ]
        )
        order.status = Order.Status.CANCELLED
        order.cancelled_at = at
        order.save(update_fields=["status", "cancelled_at", "updated_at"])
        return OrderTransitionResult(order, None, None)


def approve_simulated_payment(*, actor, order_id):
    require_administrator(actor)
    with transaction.atomic():
        order = locked_order(actor, order_id)
        history = inspect_order_history(order)
        if order.status == Order.Status.CANCELLED:
            raise OrderConflict("invalid_transition", "A cancelled order cannot receive payment.")
        if order.status != Order.Status.PENDING_PAYMENT:
            return OrderTransitionResult(order, history.simulated_payment, history.shipment)
        at = timezone.now()
        payment = SimulatedPayment.objects.create(
            order=order, amount=order.total, approved_at=at, is_simulated=True
        )
        order.status = Order.Status.PAID
        order.paid_at = at
        order.save(update_fields=["status", "paid_at", "updated_at"])
        return OrderTransitionResult(order, payment, None)


def ship_order(*, actor, order_id, tracking_code=""):
    require_administrator(actor)
    tracking_code = clean_text(tracking_code, "tracking_code", max_length=100, blank=True)
    with transaction.atomic():
        order = locked_order(actor, order_id)
        history = inspect_order_history(order)
        if order.status in {Order.Status.SHIPPED, Order.Status.DELIVERED}:
            if history.shipment.tracking_code != tracking_code:
                raise OrderConflict(
                    "tracking_conflict", "Tracking data differs from the original shipment."
                )
            return OrderTransitionResult(order, history.simulated_payment, history.shipment)
        if order.status != Order.Status.PAID:
            raise OrderConflict("invalid_transition", "Only a paid order can be shipped.")
        at = timezone.now()
        shipment = Shipment.objects.create(order=order, tracking_code=tracking_code, shipped_at=at)
        order.status = Order.Status.SHIPPED
        order.shipped_at = at
        order.save(update_fields=["status", "shipped_at", "updated_at"])
        return OrderTransitionResult(order, history.simulated_payment, shipment)


def deliver_order(*, actor, order_id):
    require_administrator(actor)
    with transaction.atomic():
        order = locked_order(actor, order_id)
        history = inspect_order_history(order)
        if order.status == Order.Status.DELIVERED:
            return OrderTransitionResult(order, history.simulated_payment, history.shipment)
        if order.status != Order.Status.SHIPPED:
            raise OrderConflict("invalid_transition", "Only a shipped order can be delivered.")
        at = timezone.now()
        shipment = history.shipment
        shipment.delivered_at = at
        shipment.save(update_fields=["delivered_at"])
        order.status = Order.Status.DELIVERED
        order.delivered_at = at
        order.save(update_fields=["status", "delivered_at", "updated_at"])
        return OrderTransitionResult(order, history.simulated_payment, shipment)

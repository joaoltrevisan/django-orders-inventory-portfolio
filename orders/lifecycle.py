"""Locked, auditable simulated order transitions; never real payment processing."""

from dataclasses import dataclass

from django.db import transaction
from django.http import Http404
from django.utils import timezone

from accounts.permissions import require_administrator
from catalog.locking import lock_offer_inventory
from common.validation import clean_text, validate_id
from inventory.services import inspect_stock

from .exceptions import OrderConflict
from .integrity import inspect_order_history
from .models import Order, Shipment, SimulatedPayment
from .reservations import database_now, release_locked_reservation
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
        if order.status == Order.Status.CANCELLED:
            _, _, _, stocks = lock_offer_inventory([item.offer_id for item in history.items])
            inspect_stock(stocks)
            return OrderTransitionResult(order, None, None)
        release_locked_reservation(order=order, history=history, actor=actor, expired=False)
        return OrderTransitionResult(order, None, None)


def approve_simulated_payment(*, actor, order_id):
    require_administrator(actor)
    with transaction.atomic():
        order = locked_order(actor, order_id)
        history = inspect_order_history(order)
        if order.status in {Order.Status.CANCELLED, Order.Status.EXPIRED}:
            raise OrderConflict(
                "invalid_transition", "A cancelled or expired order cannot receive payment."
            )
        if order.status != Order.Status.PENDING_PAYMENT:
            return OrderTransitionResult(order, history.simulated_payment, history.shipment)
        at = database_now()
        if order.reservation_expires_at is not None and at >= order.reservation_expires_at:
            raise OrderConflict(
                "reservation_expired", "The reservation payment deadline has passed."
            )
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

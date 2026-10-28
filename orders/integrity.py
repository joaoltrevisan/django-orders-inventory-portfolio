"""Cross-table order checks; caller must hold the existing order lock."""

from dataclasses import dataclass
from decimal import Decimal

from common.limits import MAX_ORDER_ITEMS

from .exceptions import OrderIntegrityConflict
from .models import Order, OrderItem, Shipment, SimulatedPayment


@dataclass(frozen=True)
class OrderHistory:
    items: list[OrderItem]
    simulated_payment: SimulatedPayment | None
    shipment: Shipment | None


def inspect_order_history(order):
    items = list(order.items.select_related("offer").order_by("offer_id"))
    if not 1 <= len(items) <= MAX_ORDER_ITEMS or order.total != sum(
        (item.subtotal for item in items), Decimal("0.00")
    ):
        raise OrderIntegrityConflict("items_or_total")
    movements = list(order.stock_movements.order_by("offer_id", "movement_type"))
    reservations = {m.offer_id: m for m in movements if m.movement_type == "RESERVATION"}
    releases = {m.offer_id: m for m in movements if m.movement_type == "RELEASE"}
    expected = {item.offer_id for item in items}
    if set(reservations) != expected or len(movements) != len(reservations) + len(releases):
        raise OrderIntegrityConflict("reservations_missing_or_extra")
    for item in items:
        movement = reservations[item.offer_id]
        if (
            movement.quantity_delta != -item.quantity
            or movement.performed_by_id != order.customer.user_id
            or movement.created_at < order.created_at
        ):
            raise OrderIntegrityConflict("reservation_mismatch")
    if order.status in {Order.Status.CANCELLED, Order.Status.EXPIRED}:
        if set(releases) != expected:
            raise OrderIntegrityConflict("releases_missing_or_extra")
        actors = {movement.performed_by_id for movement in releases.values()}
        if len(actors) != 1:
            raise OrderIntegrityConflict("release_actor_mismatch")
        released_at = (
            order.expired_at if order.status == Order.Status.EXPIRED else order.cancelled_at
        )
        for item in items:
            movement = releases[item.offer_id]
            if movement.quantity_delta != item.quantity or movement.created_at < released_at:
                raise OrderIntegrityConflict("release_mismatch")
        # The actor may be the buyer or an administrator. Current staff flags
        # cannot reconstruct historical authorization after a role change.
    elif releases:
        raise OrderIntegrityConflict("release_before_terminal_state")
    payment = SimulatedPayment.objects.filter(order=order).first()
    shipment = Shipment.objects.filter(order=order).first()
    if order.status in {Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED}:
        if (
            payment is None
            or payment.amount != order.total
            or not payment.is_simulated
            or payment.approved_at != order.paid_at
        ):
            raise OrderIntegrityConflict("payment_mismatch")
    elif payment is not None:
        raise OrderIntegrityConflict("unexpected_payment")
    if order.status in {Order.Status.SHIPPED, Order.Status.DELIVERED}:
        if (
            shipment is None
            or shipment.shipped_at != order.shipped_at
            or shipment.delivered_at != order.delivered_at
        ):
            raise OrderIntegrityConflict("shipment_mismatch")
    elif shipment is not None:
        raise OrderIntegrityConflict("unexpected_shipment")
    order.snapshot_items = items
    return OrderHistory(items, payment, shipment)

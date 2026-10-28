"""Explicit, administrator-attributed expiry of simulated stock reservations."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction

from accounts.permissions import require_administrator
from catalog.locking import lock_offer_inventory
from common.limits import MAX_STOCK_QUANTITY
from inventory.models import StockMovement
from inventory.services import inspect_stock

from .exceptions import OrderConflict
from .integrity import inspect_order_history
from .models import Order

RESERVATION_LIFETIME = timedelta(minutes=30)


def database_now():
    """Read wall time after lock waits, not the transaction's start timestamp."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT clock_timestamp()")
        return cursor.fetchone()[0]


def release_locked_reservation(*, order, history, actor, expired):
    """Caller holds the pending order lock and encloses all writes in a transaction."""
    if not connection.in_atomic_block or order.status != Order.Status.PENDING_PAYMENT:
        raise RuntimeError("Reservation release requires a locked pending-order transaction.")
    quantities = {item.offer_id: item.quantity for item in history.items}
    _, _, _, stocks = lock_offer_inventory(quantities)
    inspect_stock(stocks)
    if expired:
        require_administrator(actor)
    at = database_now()
    if expired and (order.reservation_expires_at is None or at < order.reservation_expires_at):
        return False
    if any(
        stock.available_quantity + quantities[key] > MAX_STOCK_QUANTITY
        for key, stock in stocks.items()
    ):
        raise OrderConflict(
            "stock_limit_exceeded", "Reservation release would exceed stock capacity."
        )
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
                reason=(
                    "Release on simulated reservation expiry."
                    if expired
                    else "Release on simulated order cancellation."
                ),
            )
            for key, quantity in sorted(quantities.items())
        ]
    )
    field = "expired_at" if expired else "cancelled_at"
    order.status = Order.Status.EXPIRED if expired else Order.Status.CANCELLED
    setattr(order, field, at)
    order.save(update_fields=["status", field, "updated_at"])
    return True


def expire_due_reservations(*, actor, limit=100, should_stop=None):
    """Commit each attempt separately; report failures without discarding earlier success."""
    if connection.in_atomic_block:
        raise RuntimeError("Run the expiry batch outside an enclosing transaction.")
    require_administrator(actor)
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValidationError({"limit": ["Enter an integer from 1 to 1000."]})
    cutoff = database_now()
    report = {
        "data_origin": "SIMULATED_API",
        "cutoff": cutoff.isoformat(),
        "limit": limit,
        "attempted_order_ids": [],
        "expired_order_ids": [],
        "skipped_order_ids": [],
        "failures": [],
        "stopped": False,
        "locked_skips_not_enumerated": True,
        "note": "Selected skips only; locked rows and all outstanding due orders are not counted.",
    }
    for _ in range(limit):
        if should_stop is not None and should_stop():
            report["stopped"] = True
            break
        order_id = None
        try:
            require_administrator(actor)
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update(skip_locked=True)
                    .filter(status=Order.Status.PENDING_PAYMENT, reservation_expires_at__lte=cutoff)
                    .exclude(pk__in=report["attempted_order_ids"])
                    .order_by("reservation_expires_at", "id")
                    .first()
                )
                if order is None:
                    break
                order_id = order.pk
                report["attempted_order_ids"].append(order_id)
                require_administrator(actor)
                history = inspect_order_history(order)
                changed = release_locked_reservation(
                    order=order, history=history, actor=actor, expired=True
                )
            report["expired_order_ids" if changed else "skipped_order_ids"].append(order_id)
        except (OrderConflict, DatabaseError, PermissionDenied) as error:
            code = (
                error.code
                if isinstance(error, OrderConflict)
                else (
                    "permission_denied" if isinstance(error, PermissionDenied) else "database_error"
                )
            )
            report["failures"].append({"order_id": order_id, "code": code})
            if order_id is None or isinstance(error, PermissionDenied):
                break
    report["passed"] = not report["failures"]
    return report

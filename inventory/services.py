"""Auditable stock writes and cancellation headroom at seller-offer grain."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from accounts.permissions import require_administrator
from catalog.locking import lock_offer_inventory
from common.limits import MAX_STOCK_QUANTITY
from common.validation import clean_text, validate_id
from orders.exceptions import OrderConflict, OrderIntegrityConflict
from orders.models import OrderItem

from .models import StockMovement


def inspect_stock(stocks):
    balances = dict(
        StockMovement.objects.filter(offer_id__in=stocks)
        .values("offer_id")
        .annotate(total=Sum("quantity_delta"))
        .values_list("offer_id", "total")
    )
    pending = dict(
        OrderItem.objects.filter(offer_id__in=stocks, order__status="PENDING_PAYMENT")
        .values("offer_id")
        .annotate(total=Sum("quantity"))
        .values_list("offer_id", "total")
    )
    for offer_id, stock in stocks.items():
        if stock.available_quantity != balances.get(offer_id, 0):
            raise OrderIntegrityConflict("stock_ledger_mismatch")
        if stock.available_quantity + pending.get(offer_id, 0) > MAX_STOCK_QUANTITY:
            raise OrderIntegrityConflict("cancellation_headroom_invalid")
    return pending


def change_stock(*, actor, offer_id, movement_type, quantity_delta, reason):
    require_administrator(actor)
    validate_id(offer_id)
    reason = clean_text(reason, "reason", max_length=500)
    if (
        type(quantity_delta) is not int
        or quantity_delta == 0
        or not -MAX_STOCK_QUANTITY <= quantity_delta <= MAX_STOCK_QUANTITY
    ):
        raise ValidationError(
            {"quantity_delta": ["Enter a nonzero integer within the supported stock range."]}
        )
    if (
        not isinstance(movement_type, str)
        or movement_type not in {"ENTRY", "ADJUSTMENT"}
        or (movement_type == "ENTRY" and quantity_delta < 0)
    ):
        raise ValidationError(
            {
                "movement_type": [
                    "ENTRY requires positive units; ADJUSTMENT requires a nonzero signed delta."
                ]
            }
        )
    with transaction.atomic():
        _, _, _, stocks = lock_offer_inventory([offer_id])
        pending = inspect_stock(stocks)
        stock = stocks[offer_id]
        quantity = stock.available_quantity + quantity_delta
        if (
            not 0 <= quantity <= MAX_STOCK_QUANTITY
            or quantity + pending.get(offer_id, 0) > MAX_STOCK_QUANTITY
        ):
            raise OrderConflict(
                "stock_limit_exceeded",
                "The requested change exceeds available stock or cancellation capacity.",
            )
        stock.available_quantity = quantity
        stock.save(update_fields=["available_quantity", "updated_at"])
        movement = StockMovement.objects.create(
            offer_id=offer_id,
            performed_by=actor,
            movement_type=movement_type,
            quantity_delta=quantity_delta,
            reason=reason,
        )
        return stock, movement

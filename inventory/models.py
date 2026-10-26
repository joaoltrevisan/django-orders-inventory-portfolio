from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.fields import StrictIntegerField
from common.limits import MAX_STOCK_QUANTITY


class Stock(models.Model):
    data_origin = "SIMULATED_API"
    offer = models.OneToOneField("catalog.Offer", on_delete=models.PROTECT, related_name="stock")
    available_quantity = StrictIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(MAX_STOCK_QUANTITY)]
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_stock"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(available_quantity__gte=0), name="stock_quantity_nonnegative"
            ),
        ]


class StockMovement(models.Model):
    data_origin = "SIMULATED_API"

    class Type(models.TextChoices):
        ENTRY = "ENTRY", "Entry"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        RESERVATION = "RESERVATION", "Reservation"
        RELEASE = "RELEASE", "Release"

    offer = models.ForeignKey("catalog.Offer", on_delete=models.PROTECT, related_name="movements")
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_movements"
    )
    movement_type = models.CharField(max_length=12, choices=Type.choices)
    quantity_delta = StrictIntegerField(
        validators=[MinValueValidator(-MAX_STOCK_QUANTITY), MaxValueValidator(MAX_STOCK_QUANTITY)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=500)

    class Meta:
        db_table = "inventory_stock_movement"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(movement_type="ENTRY", quantity_delta__gt=0, order__isnull=True)
                    | (
                        models.Q(movement_type="ADJUSTMENT", order__isnull=True)
                        & ~models.Q(quantity_delta=0)
                    )
                    | models.Q(
                        movement_type="RESERVATION", quantity_delta__lt=0, order__isnull=False
                    )
                    | models.Q(movement_type="RELEASE", quantity_delta__gt=0, order__isnull=False)
                ),
                name="movement_type_sign_order_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_delta__gte=-MAX_STOCK_QUANTITY),
                name="movement_delta_symmetric_range",
            ),
            models.CheckConstraint(
                condition=models.Q(reason__regex=r"\S"), name="movement_reason_required"
            ),
            models.UniqueConstraint(
                fields=["order", "offer", "movement_type"],
                condition=models.Q(movement_type__in=["RESERVATION", "RELEASE"]),
                name="movement_order_offer_type_unique",
            ),
        ]

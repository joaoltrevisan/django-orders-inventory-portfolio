import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from common.fields import StrictIntegerField
from common.limits import (
    BRAZILIAN_STATES,
    MAX_ITEM_QUANTITY,
    MAX_ORDER_TOTAL,
    MAX_UNIT_PRICE,
    SKU_PATTERN,
)
from common.models import TimestampedModel


class Order(TimestampedModel):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "Pending simulated payment"
        PAID = "PAID", "Paid (simulated)"
        SHIPPED = "SHIPPED", "Shipped (simulated)"
        DELIVERED = "DELIVERED", "Delivered (simulated)"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Reservation expired"

    customer = models.ForeignKey(
        "accounts.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)
    total = models.DecimalField(
        max_digits=16, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    currency = models.CharField(max_length=3, default="BRL", editable=False)
    shipping_recipient = models.CharField(max_length=150)
    shipping_street = models.CharField(max_length=200)
    shipping_number = models.CharField(max_length=20)
    shipping_complement = models.CharField(max_length=100, blank=True)
    shipping_district = models.CharField(max_length=100)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=2, choices=[(uf, uf) for uf in BRAZILIAN_STATES])
    shipping_postal_code = models.CharField(
        max_length=8, validators=[RegexValidator(r"^[0-9]{8}$")]
    )
    shipping_country = models.CharField(max_length=2, default="BR", editable=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    reservation_expires_at = models.DateTimeField(null=True, blank=True, editable=False)
    expired_at = models.DateTimeField(null=True, blank=True, editable=False)
    idempotency_key_hash = models.CharField(max_length=64, null=True, blank=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, null=True, blank=True, editable=False)

    class Meta:
        db_table = "orders_order"
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "idempotency_key_hash"],
                condition=models.Q(idempotency_key_hash__isnull=False),
                name="order_customer_idempotency_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(idempotency_key_hash__isnull=True, request_fingerprint__isnull=True)
                    | models.Q(
                        idempotency_key_hash__isnull=False,
                        request_fingerprint__isnull=False,
                        idempotency_key_hash__regex=r"^[0-9a-f]{64}$",
                        request_fingerprint__regex=r"^[0-9a-f]{64}$",
                    )
                ),
                name="order_idempotency_hash_pair_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(total__gt=0, total__lte=MAX_ORDER_TOTAL),
                name="order_total_positive_finite",
            ),
            models.CheckConstraint(condition=models.Q(currency="BRL"), name="order_currency_brl"),
            models.CheckConstraint(
                condition=(
                    models.Q(shipping_country="BR", shipping_state__in=BRAZILIAN_STATES)
                    & models.Q(shipping_postal_code__regex=r"^[0-9]{8}$")
                    & models.Q(shipping_recipient__regex=r"\S")
                    & models.Q(shipping_street__regex=r"\S")
                    & models.Q(shipping_number__regex=r"\S")
                    & models.Q(shipping_district__regex=r"\S")
                    & models.Q(shipping_city__regex=r"\S")
                ),
                name="order_shipping_address_valid",
            ),
            # This CHECK compares only this order row, never another table.
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="PENDING_PAYMENT",
                        paid_at__isnull=True,
                        expired_at__isnull=True,
                        cancelled_at__isnull=True,
                        shipped_at__isnull=True,
                        delivered_at__isnull=True,
                    )
                    | models.Q(
                        status="CANCELLED",
                        paid_at__isnull=True,
                        expired_at__isnull=True,
                        cancelled_at__isnull=False,
                        shipped_at__isnull=True,
                        delivered_at__isnull=True,
                    )
                    | models.Q(
                        status="EXPIRED",
                        paid_at__isnull=True,
                        cancelled_at__isnull=True,
                        shipped_at__isnull=True,
                        delivered_at__isnull=True,
                        expired_at__isnull=False,
                        reservation_expires_at__isnull=False,
                    )
                    | models.Q(
                        status="PAID",
                        paid_at__isnull=False,
                        expired_at__isnull=True,
                        cancelled_at__isnull=True,
                        shipped_at__isnull=True,
                        delivered_at__isnull=True,
                    )
                    | models.Q(
                        status="SHIPPED",
                        paid_at__isnull=False,
                        expired_at__isnull=True,
                        cancelled_at__isnull=True,
                        shipped_at__isnull=False,
                        delivered_at__isnull=True,
                    )
                    | models.Q(
                        status="DELIVERED",
                        paid_at__isnull=False,
                        expired_at__isnull=True,
                        cancelled_at__isnull=True,
                        shipped_at__isnull=False,
                        delivered_at__isnull=False,
                    )
                ),
                name="order_status_timestamps_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(reservation_expires_at__isnull=True)
                        | models.Q(reservation_expires_at__gt=models.F("created_at"))
                    )
                    & (
                        models.Q(expired_at__isnull=True)
                        | (
                            models.Q(reservation_expires_at__isnull=False)
                            & models.Q(expired_at__gte=models.F("reservation_expires_at"))
                        )
                    )
                    & (
                        models.Q(paid_at__isnull=True)
                        | models.Q(reservation_expires_at__isnull=True)
                        | models.Q(paid_at__lt=models.F("reservation_expires_at"))
                    )
                ),
                name="order_reservation_timestamps_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (models.Q(paid_at__isnull=True) | models.Q(paid_at__gte=models.F("created_at")))
                    & (
                        models.Q(cancelled_at__isnull=True)
                        | models.Q(cancelled_at__gte=models.F("created_at"))
                    )
                    & (
                        models.Q(shipped_at__isnull=True)
                        | models.Q(shipped_at__gte=models.F("paid_at"))
                    )
                    & (
                        models.Q(delivered_at__isnull=True)
                        | models.Q(delivered_at__gte=models.F("shipped_at"))
                    )
                ),
                name="order_timestamps_chronological",
            ),
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    offer = models.ForeignKey("catalog.Offer", on_delete=models.PROTECT, related_name="order_items")
    quantity = StrictIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_ITEM_QUANTITY)]
    )
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    product_sku = models.CharField(max_length=64, validators=[RegexValidator(SKU_PATTERN)])
    product_name = models.CharField(max_length=200)
    seller_label = models.CharField(max_length=200)

    class Meta:
        db_table = "orders_order_item"
        constraints = [
            models.UniqueConstraint(fields=["order", "offer"], name="item_order_offer_unique"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=MAX_ITEM_QUANTITY),
                name="item_quantity_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gt=0, unit_price__lte=MAX_UNIT_PRICE),
                name="item_price_positive_finite",
            ),
            models.CheckConstraint(
                condition=models.Q(product_sku__regex=SKU_PATTERN)
                & models.Q(product_name__regex=r"\S")
                & models.Q(seller_label__regex=r"\S"),
                name="item_snapshot_required",
            ),
        ]

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


class SimulatedPayment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="simulated_payment")
    amount = models.DecimalField(
        max_digits=16, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    approved_at = models.DateTimeField()
    is_simulated = models.BooleanField(default=True, editable=False)

    class Meta:
        db_table = "orders_simulated_payment"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0, amount__lte=MAX_ORDER_TOTAL),
                name="payment_amount_positive_finite",
            ),
            models.CheckConstraint(
                condition=models.Q(is_simulated=True), name="payment_simulation_required"
            ),
        ]

    def __str__(self):
        return f"SIMULATED PAYMENT {self.reference} - NO REAL CHARGE"


class Shipment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="shipment")
    tracking_code = models.CharField(max_length=100, blank=True)
    shipped_at = models.DateTimeField()
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders_shipment"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(delivered_at__isnull=True)
                | models.Q(delivered_at__gte=models.F("shipped_at")),
                name="shipment_dates_chronological",
            ),
        ]

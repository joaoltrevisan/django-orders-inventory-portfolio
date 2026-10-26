from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from common.limits import MAX_UNIT_PRICE, SKU_PATTERN
from common.models import TimestampedModel


class Product(TimestampedModel):
    """Fictional demonstration product; current prices belong to offers."""

    sku = models.CharField(max_length=64, unique=True, validators=[RegexValidator(SKU_PATTERN)])
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(sku__regex=SKU_PATTERN), name="product_sku_format"
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=r"\S"), name="product_name_required"
            ),
        ]


class Seller(TimestampedModel):
    label = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(label__regex=r"\S"), name="seller_label_required"
            ),
        ]


class Offer(TimestampedModel):
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name="offers")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="offers")
    simulated_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seller", "product"], name="offer_seller_product_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(simulated_price__gt=0, simulated_price__lte=MAX_UNIT_PRICE),
                name="offer_price_positive_finite",
            ),
        ]

"""Catalog writes follow seller, product, offer, then stock lock order."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from accounts.permissions import require_administrator
from inventory.models import Stock

from .models import Offer, Product, Seller


def require_admin(actor):
    require_administrator(actor)


def save_product(*, actor, data, pk=None):
    require_admin(actor)
    if set(data) - {"sku", "name", "description", "is_active"}:
        raise ValidationError("Invalid product fields.")
    try:
        with transaction.atomic():
            product = (
                get_object_or_404(Product.objects.select_for_update(), pk=pk) if pk else Product()
            )
            if pk and "sku" in data and data["sku"] != product.sku:
                raise ValidationError({"sku": ["SKU cannot be changed."]})
            for field, value in data.items():
                setattr(product, field, value)
            product.full_clean()
            product.save()
            return product
    except IntegrityError as error:
        if getattr(error.__cause__, "sqlstate", None) == "23505":
            raise ValidationError({"sku": ["SKU is already registered."]}) from error
        raise


def save_seller(*, actor, data, pk=None):
    require_admin(actor)
    if set(data) - {"label", "is_active"}:
        raise ValidationError("Invalid seller fields.")
    with transaction.atomic():
        seller = get_object_or_404(Seller.objects.select_for_update(), pk=pk) if pk else Seller()
        for field, value in data.items():
            setattr(seller, field, value)
        seller.full_clean()
        seller.save()
        return seller


def save_offer(*, actor, data, pk=None):
    require_admin(actor)
    if set(data) - {"seller_id", "product_id", "simulated_price", "is_active"}:
        raise ValidationError("Invalid offer fields.")
    try:
        with transaction.atomic():
            if pk:
                identity = get_object_or_404(Offer, pk=pk)
                seller_id, product_id = identity.seller_id, identity.product_id
                if any(
                    field in data and data[field] != getattr(identity, field)
                    for field in ["seller_id", "product_id"]
                ):
                    raise ValidationError("Offer seller and product cannot be changed.")
            else:
                if not {"seller_id", "product_id", "simulated_price"}.issubset(data):
                    raise ValidationError("Seller, product and simulated price are required.")
                seller_id, product_id = data["seller_id"], data["product_id"]
            get_object_or_404(Seller.objects.select_for_update(), pk=seller_id)
            get_object_or_404(Product.objects.select_for_update(), pk=product_id)
            offer = get_object_or_404(Offer.objects.select_for_update(), pk=pk) if pk else Offer()
            for field, value in data.items():
                setattr(offer, field, value)
            offer.full_clean()
            offer.save()
            if not pk:
                Stock.objects.create(offer=offer, available_quantity=0)
            return offer
    except IntegrityError as error:
        if getattr(error.__cause__, "sqlstate", None) == "23505":
            raise ValidationError("This seller already has an offer for the product.") from error
        raise

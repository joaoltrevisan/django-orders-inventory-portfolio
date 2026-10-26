"""Shared offer inventory locking; call only inside an atomic transaction."""

from inventory.models import Stock
from orders.exceptions import OrderConflict

from .models import Offer, Product, Seller


def lock_offer_inventory(offer_ids):
    ids = sorted(set(offer_ids))
    identities = list(Offer.objects.filter(pk__in=ids).values("id", "seller_id", "product_id"))
    if len(identities) != len(ids):
        raise OrderConflict("offer_unavailable", "One or more offers are unavailable.")
    seller_ids = sorted({row["seller_id"] for row in identities})
    product_ids = sorted({row["product_id"] for row in identities})
    # Fully evaluate every layer before advancing; avoid implicit joined parent locks.
    sellers = {
        row.pk: row
        for row in Seller.objects.select_for_update().filter(pk__in=seller_ids).order_by("id")
    }
    products = {
        row.pk: row
        for row in Product.objects.select_for_update().filter(pk__in=product_ids).order_by("id")
    }
    offers = list(Offer.objects.select_for_update().filter(pk__in=ids).order_by("id"))
    stocks = {
        row.offer_id: row
        for row in Stock.objects.select_for_update().filter(offer_id__in=ids).order_by("offer_id")
    }
    if (
        len(sellers) != len(seller_ids)
        or len(products) != len(product_ids)
        or len(offers) != len(ids)
        or len(stocks) != len(ids)
    ):
        raise OrderConflict("stock_unavailable", "Offer inventory has not been initialized.")
    return offers, sellers, products, stocks

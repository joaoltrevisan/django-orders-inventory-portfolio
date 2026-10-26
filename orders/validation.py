"""Service-level input validation, adapted from the existing order API."""

from django.core.exceptions import ValidationError

from common.limits import MAX_ITEM_QUANTITY, MAX_ORDER_ITEMS
from common.validation import MAX_ID, clean_text

from .models import Order

ADDRESS_FIELDS = (
    "recipient",
    "street",
    "number",
    "complement",
    "district",
    "city",
    "state",
    "postal_code",
)


def validate_order_input(*, items, shipping_address):
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ORDER_ITEMS:
        raise ValidationError({"items": [f"Provide 1 to {MAX_ORDER_ITEMS} offer lines."]})
    seen = set()
    result = []
    for number, item in enumerate(items, 1):
        if not isinstance(item, dict) or set(item) != {"offer_id", "quantity"}:
            raise ValidationError(
                {"items": [f"Line {number}: only offer_id and quantity are permitted."]}
            )
        offer_id, quantity = item["offer_id"], item["quantity"]
        if type(offer_id) is not int or not 1 <= offer_id <= MAX_ID:
            raise ValidationError({"items": [f"Line {number}: enter a positive integer offer_id."]})
        if type(quantity) is not int or not 1 <= quantity <= MAX_ITEM_QUANTITY:
            raise ValidationError(
                {
                    "items": [
                        f"Line {number}: quantity must be an integer from 1 to {MAX_ITEM_QUANTITY}."
                    ]
                }
            )
        if offer_id in seen:
            raise ValidationError({"items": [f"Offer {offer_id} occurs more than once."]})
        seen.add(offer_id)
        result.append({"offer_id": offer_id, "quantity": quantity})
    required = set(ADDRESS_FIELDS) - {"complement"}
    if (
        not isinstance(shipping_address, dict)
        or set(shipping_address) - set(ADDRESS_FIELDS)
        or required - set(shipping_address)
    ):
        raise ValidationError(
            {
                "shipping_address": [
                    "Provide recipient, street, number, district, city, state and postal_code; "
                    "complement is optional. Other fields are not permitted."
                ]
            }
        )
    address = {}
    for name in ADDRESS_FIELDS:
        field = Order._meta.get_field("shipping_" + name)
        value = clean_text(
            shipping_address.get(name, ""),
            name,
            max_length=field.max_length,
            blank=name == "complement",
        )
        address[name] = field.clean(value, None)
    return result, address

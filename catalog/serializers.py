from decimal import Decimal

from rest_framework import serializers

from common.serializers import JSONBooleanField, MoneyInputField, StrictInputMixin, TextField

from .models import Offer, Product, Seller


class ProductSerializer(StrictInputMixin, serializers.ModelSerializer):
    name = TextField(max_length=200)
    description = TextField(max_length=5000, allow_blank=True, required=False)
    is_active = JSONBooleanField(required=False)
    data_origin = serializers.CharField(default="SIMULATED_API", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "sku", "name", "description", "is_active", "data_origin"]
        read_only_fields = ["id"]


class SellerSerializer(StrictInputMixin, serializers.ModelSerializer):
    label = TextField(max_length=200)
    is_active = JSONBooleanField(required=False)
    data_origin = serializers.CharField(default="SIMULATED_API", read_only=True)

    class Meta:
        model = Seller
        fields = ["id", "label", "is_active", "data_origin"]
        read_only_fields = ["id"]


class IdentityField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            raise serializers.ValidationError("Enter an integer JSON identity.")
        return super().to_internal_value(data)


class OfferSerializer(StrictInputMixin, serializers.ModelSerializer):
    seller_id = IdentityField(min_value=1, max_value=9223372036854775807)
    product_id = IdentityField(min_value=1, max_value=9223372036854775807)
    simulated_price = MoneyInputField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    is_active = JSONBooleanField(required=False)
    available_quantity = serializers.IntegerField(source="stock.available_quantity", read_only=True)
    data_origin = serializers.CharField(default="SIMULATED_API", read_only=True)

    class Meta:
        model = Offer
        fields = [
            "id",
            "seller_id",
            "product_id",
            "simulated_price",
            "is_active",
            "available_quantity",
            "data_origin",
        ]
        read_only_fields = ["id"]
        validators = []  # The locked service checks the seller/product composite identity.

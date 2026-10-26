"""Read-only historical representations preserve source clocks and identifiers."""

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from .fields import SourceDateTimeField
from .models import (
    Category,
    HistoricalCustomer,
    HistoricalOrder,
    HistoricalOrderItem,
    HistoricalPaymentRecord,
    HistoricalProduct,
    HistoricalSeller,
)


@extend_schema_field({"type": "string", "example": "2017-03-01 00:15:00"})
class SourceClockField(serializers.Field):
    def to_representation(self, value):
        return value.strftime("%Y-%m-%d %H:%M:%S") if value is not None else None


class HistoricalSerializer(serializers.ModelSerializer):
    data_origin = serializers.CharField(default="OLIST_HISTORICAL", read_only=True)

    def build_standard_field(self, field_name, model_field):
        if isinstance(model_field, SourceDateTimeField):
            return SourceClockField, {"read_only": True, "allow_null": model_field.null}
        return super().build_standard_field(field_name, model_field)

    def get_fields(self):
        fields = super().get_fields()
        for field in fields.values():
            field.read_only = True
        return fields


@extend_schema_serializer(component_name="HistoricalCustomer")
class CustomerSerializer(HistoricalSerializer):
    class Meta:
        model = HistoricalCustomer
        fields = "__all__"


@extend_schema_serializer(component_name="HistoricalCategory")
class CategorySerializer(HistoricalSerializer):
    class Meta:
        model = Category
        fields = "__all__"


@extend_schema_serializer(component_name="HistoricalProduct")
class ProductSerializer(HistoricalSerializer):
    category = serializers.SlugRelatedField(slug_field="source_name", read_only=True)

    class Meta:
        model = HistoricalProduct
        fields = "__all__"


@extend_schema_serializer(component_name="HistoricalSeller")
class SellerSerializer(HistoricalSerializer):
    class Meta:
        model = HistoricalSeller
        fields = "__all__"


@extend_schema_serializer(component_name="HistoricalOrder")
class OrderSerializer(HistoricalSerializer):
    customer = serializers.SlugRelatedField(slug_field="source_customer_id", read_only=True)
    customer_unique_id = serializers.CharField(source="customer.customer_unique_id", read_only=True)

    class Meta:
        model = HistoricalOrder
        fields = "__all__"


@extend_schema_serializer(component_name="HistoricalItem")
class ItemSerializer(HistoricalSerializer):
    order = serializers.SlugRelatedField(slug_field="source_order_id", read_only=True)
    product = serializers.SlugRelatedField(slug_field="source_product_id", read_only=True)
    seller = serializers.SlugRelatedField(slug_field="source_seller_id", read_only=True)

    class Meta:
        model = HistoricalOrderItem
        fields = "__all__"


@extend_schema_serializer(component_name="HistoricalPaymentRecord")
class PaymentSerializer(HistoricalSerializer):
    order = serializers.SlugRelatedField(slug_field="source_order_id", read_only=True)
    payment_record_kind = serializers.CharField(default="HISTORICAL_RECORD", read_only=True)

    class Meta:
        model = HistoricalPaymentRecord
        fields = "__all__"

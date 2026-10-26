from django.core.validators import RegexValidator
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from common.limits import BRAZILIAN_STATES, MAX_ITEM_QUANTITY, MAX_ORDER_ITEMS
from common.serializers import JSONIntegerField, StrictInputMixin, TextField
from common.validation import MAX_ID

from .models import Order, OrderItem, Shipment, SimulatedPayment
from .validation import ADDRESS_FIELDS


class OrderItemInputSerializer(StrictInputMixin, serializers.Serializer):
    offer_id = JSONIntegerField(min_value=1, max_value=MAX_ID)
    quantity = JSONIntegerField(min_value=1, max_value=MAX_ITEM_QUANTITY)


class ShippingAddressInputSerializer(StrictInputMixin, serializers.Serializer):
    recipient = TextField(max_length=150)
    street = TextField(max_length=200)
    number = TextField(max_length=20)
    complement = TextField(max_length=100, allow_blank=True, required=False)
    district = TextField(max_length=100)
    city = TextField(max_length=100)
    state = serializers.ChoiceField(choices=BRAZILIAN_STATES)
    postal_code = TextField(max_length=8, validators=[RegexValidator(r"^[0-9]{8}$")])


class OrderCreateSerializer(StrictInputMixin, serializers.Serializer):
    items = OrderItemInputSerializer(many=True, allow_empty=False, max_length=MAX_ORDER_ITEMS)
    shipping_address = ShippingAddressInputSerializer()


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="offer.product_id", read_only=True)
    seller_id = serializers.IntegerField(source="offer.seller_id", read_only=True)
    subtotal = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "offer_id",
            "product_id",
            "seller_id",
            "product_sku",
            "product_name",
            "seller_label",
            "quantity",
            "unit_price",
            "subtotal",
        ]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()
    data_origin = serializers.CharField(default="SIMULATED_API", read_only=True)
    payment_mode = serializers.CharField(default="SIMULATED_NO_REAL_CHARGE", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_id",
            "status",
            "currency",
            "total",
            "shipping_address",
            "items",
            "created_at",
            "updated_at",
            "paid_at",
            "cancelled_at",
            "shipped_at",
            "delivered_at",
            "data_origin",
            "payment_mode",
        ]
        read_only_fields = fields

    @extend_schema_field(OrderItemSerializer(many=True))
    def get_items(self, order):
        items = getattr(order, "snapshot_items", None)
        if items is None:
            items = order.items.select_related("offer").order_by("offer_id")
        return OrderItemSerializer(items, many=True).data

    def get_shipping_address(self, order) -> dict[str, str]:
        return {name: getattr(order, "shipping_" + name) for name in (*ADDRESS_FIELDS, "country")}


class SimulatedPaymentSerializer(serializers.ModelSerializer):
    payment_record_kind = serializers.CharField(
        default="SIMULATED_APPROVAL_NO_REAL_CHARGE", read_only=True
    )
    data_origin = serializers.CharField(default="SIMULATED_API", read_only=True)

    class Meta:
        model = SimulatedPayment
        fields = [
            "id",
            "amount",
            "reference",
            "approved_at",
            "is_simulated",
            "data_origin",
            "payment_record_kind",
        ]
        read_only_fields = fields


class ShipmentSerializer(serializers.ModelSerializer):
    data_origin = serializers.CharField(default="SIMULATED_API", read_only=True)

    class Meta:
        model = Shipment
        fields = ["id", "tracking_code", "shipped_at", "delivered_at", "data_origin"]
        read_only_fields = fields


class OrderDetailSerializer(OrderSerializer):
    simulated_payment = SimulatedPaymentSerializer(read_only=True, allow_null=True)
    shipment = ShipmentSerializer(read_only=True, allow_null=True)

    class Meta(OrderSerializer.Meta):
        fields = [*OrderSerializer.Meta.fields, "simulated_payment", "shipment"]
        read_only_fields = fields


class OrderTransitionSerializer(serializers.Serializer):
    order = OrderSerializer(read_only=True)
    simulated_payment = SimulatedPaymentSerializer(read_only=True, allow_null=True)
    shipment = ShipmentSerializer(read_only=True, allow_null=True)


class EmptyActionSerializer(StrictInputMixin, serializers.Serializer):
    pass


class ShippingActionSerializer(StrictInputMixin, serializers.Serializer):
    tracking_code = TextField(max_length=100, allow_blank=True, required=False, default="")

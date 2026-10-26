from rest_framework import serializers

from common.limits import MAX_STOCK_QUANTITY
from common.serializers import JSONIntegerField, StrictInputMixin, TextField

from .models import Stock, StockMovement


class StockSerializer(serializers.ModelSerializer):
    data_origin = serializers.CharField(default="SIMULATED_API", read_only=True)

    class Meta:
        model = Stock
        fields = ["offer_id", "available_quantity", "updated_at", "data_origin"]
        read_only_fields = fields


class MovementSerializer(serializers.ModelSerializer):
    data_origin = serializers.CharField(default="SIMULATED_API", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "offer_id",
            "order_id",
            "performed_by_id",
            "movement_type",
            "quantity_delta",
            "created_at",
            "reason",
            "data_origin",
        ]
        read_only_fields = fields


class StockChangeSerializer(StrictInputMixin, serializers.Serializer):
    movement_type = serializers.ChoiceField(choices=["ENTRY", "ADJUSTMENT"])
    quantity_delta = JSONIntegerField(min_value=-MAX_STOCK_QUANTITY, max_value=MAX_STOCK_QUANTITY)
    reason = TextField(max_length=500)


class StockChangeResultSerializer(serializers.Serializer):
    stock = StockSerializer(read_only=True)
    movement = MovementSerializer(read_only=True)

import re

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from accounts.permissions import IsAdministrator
from common.api import PrivateResponseMixin

from .models import (
    Category,
    HistoricalCustomer,
    HistoricalOrder,
    HistoricalOrderItem,
    HistoricalPaymentRecord,
    HistoricalProduct,
    HistoricalSeller,
)
from .serializers import (
    CategorySerializer,
    CustomerSerializer,
    ItemSerializer,
    OrderSerializer,
    PaymentSerializer,
    ProductSerializer,
    SellerSerializer,
)


class HistoricalViewSet(PrivateResponseMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdministrator]
    http_method_names = ["get", "head", "options"]
    parent_path = "snapshot"
    allow_order_filter = False

    def get_queryset(self):
        queryset = (
            super().get_queryset().filter(**{self.parent_path + "__publication_status": "COMPLETE"})
        )
        if self.allow_order_filter and "order_id" in self.request.query_params:
            source_id = self.request.query_params["order_id"]
            if not re.fullmatch(r"[0-9a-f]{32}", source_id):
                raise ValidationError({"order_id": "Enter a 32-character source order identifier."})
            queryset = queryset.filter(order__source_order_id=source_id)
        return queryset


class CustomerViewSet(HistoricalViewSet):
    serializer_class = CustomerSerializer
    queryset = HistoricalCustomer.objects.order_by("source_customer_id")
    lookup_field = "source_customer_id"


class CategoryViewSet(HistoricalViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.order_by("source_name")
    lookup_field = "source_name"


class ProductViewSet(HistoricalViewSet):
    serializer_class = ProductSerializer
    queryset = HistoricalProduct.objects.select_related("category").order_by("source_product_id")
    lookup_field = "source_product_id"


class SellerViewSet(HistoricalViewSet):
    serializer_class = SellerSerializer
    queryset = HistoricalSeller.objects.order_by("source_seller_id")
    lookup_field = "source_seller_id"


class OrderViewSet(HistoricalViewSet):
    serializer_class = OrderSerializer
    queryset = HistoricalOrder.objects.select_related("customer").order_by("source_order_id")
    lookup_field = "source_order_id"


class ItemViewSet(HistoricalViewSet):
    serializer_class = ItemSerializer
    queryset = HistoricalOrderItem.objects.select_related("order", "product", "seller").order_by(
        "order__source_order_id", "source_order_item_id"
    )
    parent_path = "order__snapshot"
    allow_order_filter = True


class PaymentViewSet(HistoricalViewSet):
    serializer_class = PaymentSerializer
    queryset = HistoricalPaymentRecord.objects.select_related("order").order_by(
        "order__source_order_id", "payment_sequential"
    )
    parent_path = "order__snapshot"
    allow_order_filter = True

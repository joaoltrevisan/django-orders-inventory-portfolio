from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CanAccessOrder, IsAdministrator, IsCustomer, is_administrator
from common.api import PrivateResponseMixin, service_call
from common.validation import validate_id

from .lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from .models import Order, OrderItem
from .selectors import orders_visible_to
from .serializers import (
    EmptyActionSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderSerializer,
    OrderTransitionSerializer,
    ShippingActionSerializer,
)
from .services import create_order


def readable_orders(actor):
    return (
        orders_visible_to(actor)
        .select_related("customer", "simulated_payment", "shipment")
        .prefetch_related(
            Prefetch(
                "items",
                queryset=OrderItem.objects.select_related("offer").order_by("offer_id"),
                to_attr="snapshot_items",
            )
        )
        .order_by("id")
    )


class OrderListView(PrivateResponseMixin, generics.ListAPIView):
    serializer_class = OrderDetailSerializer

    def get_permissions(self):
        return [IsCustomer()] if self.request.method == "POST" else [CanAccessOrder()]

    def get_queryset(self):
        queryset = readable_orders(self.request.user)
        if "status" in self.request.query_params:
            value = self.request.query_params["status"]
            if value not in Order.Status.values:
                raise ValidationError({"status": ["Enter a valid operational order status."]})
            queryset = queryset.filter(status=value)
        if "customer_id" in self.request.query_params:
            if not is_administrator(self.request.user):
                raise PermissionDenied("Only administrators can filter by customer.")
            field = serializers.IntegerField(min_value=1, max_value=9223372036854775807)
            queryset = queryset.filter(
                customer_id=field.run_validation(self.request.query_params["customer_id"])
            )
        return queryset

    @extend_schema(request=OrderCreateSerializer, responses={201: OrderSerializer})
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = service_call(create_order, actor=request.user, **serializer.validated_data)
        return Response(OrderSerializer(order).data, status=201)


class OrderDetailView(PrivateResponseMixin, generics.RetrieveAPIView):
    permission_classes = [CanAccessOrder]
    serializer_class = OrderDetailSerializer
    lookup_url_kwarg = "order_id"

    def get_queryset(self):
        return readable_orders(self.request.user)


class OrderActionView(PrivateResponseMixin, APIView):
    permission_classes = [IsAdministrator]
    serializer_class = EmptyActionSerializer

    @extend_schema(responses=OrderTransitionSerializer)
    def post(self, request, order_id):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = service_call(
            self.transition,
            actor=request.user,
            order_id=validate_id(order_id),
            **serializer.validated_data,
        )
        return Response(OrderTransitionSerializer(result).data)


class OrderCancelView(OrderActionView):
    permission_classes = [CanAccessOrder]
    transition = staticmethod(cancel_order)


class OrderPaymentView(OrderActionView):
    transition = staticmethod(approve_simulated_payment)


class OrderShipView(OrderActionView):
    serializer_class = ShippingActionSerializer
    transition = staticmethod(ship_order)


class OrderDeliverView(OrderActionView):
    transition = staticmethod(deliver_order)

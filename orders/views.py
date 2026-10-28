from django.db.models import Prefetch
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
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


@extend_schema_view(
    get=extend_schema(
        description="Owner-scoped orders; administrators see all orders. Page size 20.",
        parameters=[
            OpenApiParameter("status", str, enum=Order.Status.values),
            OpenApiParameter(
                "customer_id", int, description="Administrator only; Customer profile PK."
            ),
        ],
    )
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

    @extend_schema(
        description=(
            "Create a simulated order. Optional customer-scoped key enables safe retry; "
            "replay returns current stored state without reserving again or renewing its "
            "deadline. New orders have a fixed 30-minute reservation payment deadline."
        ),
        request=OrderCreateSerializer,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key",
                str,
                OpenApiParameter.HEADER,
                description=(
                    "Optional, case-sensitive 1–128 ASCII letters/digits or . _ : -. "
                    "Retained with the order; same normalized content replays, "
                    "different content conflicts."
                ),
            ),
            OpenApiParameter(
                "Idempotency-Replayed",
                bool,
                OpenApiParameter.HEADER,
                description=(
                    "Present on successful keyed requests: false for creation, true for replay."
                ),
                response=[200, 201],
            ),
        ],
        responses={
            201: OrderSerializer,
            200: OrderSerializer,
            400: OpenApiResponse(
                OpenApiTypes.OBJECT, description="Invalid content or creation key."
            ),
            409: OpenApiResponse(
                OpenApiTypes.OBJECT,
                description=(
                    "Idempotency-content conflict, insufficient stock or another business conflict."
                ),
            ),
        },
    )
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key")
        order = service_call(
            create_order, actor=request.user, idempotency_key=key, **serializer.validated_data
        )
        headers = (
            {"Idempotency-Replayed": str(order.idempotency_replayed).lower()}
            if key is not None
            else {}
        )
        return Response(
            OrderSerializer(order).data,
            status=200 if order.idempotency_replayed else 201,
            headers=headers,
        )


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


@extend_schema_view(
    post=extend_schema(
        description=(
            "Cancel a pending order, including overdue pending reservations. EXPIRED is terminal."
        ),
    )
)
class OrderCancelView(OrderActionView):
    permission_classes = [CanAccessOrder]
    transition = staticmethod(cancel_order)


@extend_schema_view(
    post=extend_schema(
        description=(
            "Simulated approval only; pending orders require PostgreSQL wall time strictly "
            "before their reservation deadline. Legacy NULL deadlines remain payable. "
            "Overdue pending returns reservation_expired (409) without releasing stock; "
            "EXPIRED is terminal."
        ),
        responses={
            200: OrderTransitionSerializer,
            409: OpenApiResponse(
                OpenApiTypes.OBJECT,
                description="Reservation deadline passed or invalid transition.",
            ),
        },
    )
)
class OrderPaymentView(OrderActionView):
    transition = staticmethod(approve_simulated_payment)


class OrderShipView(OrderActionView):
    serializer_class = ShippingActionSerializer
    transition = staticmethod(ship_order)


class OrderDeliverView(OrderActionView):
    transition = staticmethod(deliver_order)

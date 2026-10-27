from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator
from common.api import PrivateResponseMixin, service_call

from .models import Stock, StockMovement
from .serializers import (
    MovementSerializer,
    StockChangeResultSerializer,
    StockChangeSerializer,
    StockSerializer,
)
from .services import change_stock


class StockListView(PrivateResponseMixin, generics.ListAPIView):
    permission_classes = [IsAdministrator]
    serializer_class = StockSerializer
    queryset = Stock.objects.order_by("offer_id")


class StockDetailView(PrivateResponseMixin, generics.RetrieveAPIView):
    permission_classes = [IsAdministrator]
    serializer_class = StockSerializer
    queryset = Stock.objects.order_by("offer_id")
    lookup_field = "offer_id"


class StockChangeView(PrivateResponseMixin, APIView):
    permission_classes = [IsAdministrator]
    serializer_class = StockChangeSerializer

    @extend_schema(responses={201: StockChangeResultSerializer})
    def post(self, request, offer_id):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        get_object_or_404(Stock, offer_id=offer_id)
        stock, movement = service_call(
            change_stock, actor=request.user, offer_id=offer_id, **serializer.validated_data
        )
        return Response(
            {"stock": StockSerializer(stock).data, "movement": MovementSerializer(movement).data},
            status=201,
        )


@extend_schema_view(
    get=extend_schema(
        description="Administrator-only immutable simulated stock movements. Page size 20.",
        parameters=[OpenApiParameter("offer_id", int), OpenApiParameter("order_id", int)],
    )
)
class MovementListView(PrivateResponseMixin, generics.ListAPIView):
    permission_classes = [IsAdministrator]
    serializer_class = MovementSerializer

    def get_queryset(self):
        queryset = StockMovement.objects.order_by("id")
        for field in ["offer_id", "order_id"]:
            if field in self.request.query_params:
                value = serializers.IntegerField(
                    min_value=1, max_value=9223372036854775807
                ).run_validation(self.request.query_params[field])
                queryset = queryset.filter(**{field: value})
        return queryset

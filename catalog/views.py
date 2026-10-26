from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdministrator, is_administrator
from common.api import PrivateResponseMixin, service_call

from .models import Offer, Product, Seller
from .serializers import OfferSerializer, ProductSerializer, SellerSerializer
from .services import save_offer, save_product, save_seller


class CatalogViewSet(PrivateResponseMixin, viewsets.GenericViewSet):
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        return (
            [IsAuthenticated()]
            if self.request.method in {"GET", "HEAD", "OPTIONS"}
            else [IsAdministrator()]
        )

    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    def create(self, request):
        return self.write(request)

    def partial_update(self, request, *args, **kwargs):
        return self.write(request, self.get_object().pk)

    def write(self, request, pk=None):
        serializer = self.get_serializer(data=request.data, partial=pk is not None)
        serializer.is_valid(raise_exception=True)
        instance = service_call(
            self.service, actor=request.user, data=serializer.validated_data, pk=pk
        )
        return Response(
            self.get_serializer(instance).data, status=200 if pk else status.HTTP_201_CREATED
        )


class ProductViewSet(CatalogViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.order_by("id")
    service = staticmethod(save_product)

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_administrator(self.request.user) else queryset.filter(is_active=True)


class SellerViewSet(CatalogViewSet):
    serializer_class = SellerSerializer
    queryset = Seller.objects.order_by("id")
    service = staticmethod(save_seller)

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_administrator(self.request.user) else queryset.filter(is_active=True)


class OfferViewSet(CatalogViewSet):
    serializer_class = OfferSerializer
    queryset = Offer.objects.select_related("stock").order_by("id")
    service = staticmethod(save_offer)

    def get_queryset(self):
        queryset = super().get_queryset()
        return (
            queryset
            if is_administrator(self.request.user)
            else queryset.filter(is_active=True, seller__is_active=True, product__is_active=True)
        )

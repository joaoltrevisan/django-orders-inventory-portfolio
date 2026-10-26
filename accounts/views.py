from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from common.api import PrivateResponseMixin, service_call

from .models import Customer
from .permissions import IsAdministrator
from .serializers import (
    ActiveUserRefreshSerializer,
    CustomerSerializer,
    CustomerUpdateSerializer,
    LoginSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    RegistrationSerializer,
)
from .services import manage_customer, update_profile


class RegistrationView(PrivateResponseMixin, APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_scope = "register"

    @extend_schema(request=RegistrationSerializer, responses={201: ProfileSerializer})
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(ProfileSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


class LoginView(PrivateResponseMixin, TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_scope = "login"


class RefreshView(PrivateResponseMixin, TokenRefreshView):
    serializer_class = ActiveUserRefreshSerializer
    throttle_scope = "refresh"


class ProfileView(PrivateResponseMixin, APIView):
    @extend_schema(responses=ProfileSerializer)
    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    @extend_schema(request=ProfileUpdateSerializer, responses=ProfileSerializer)
    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = service_call(update_profile, user=request.user, **serializer.validated_data)
        return Response(ProfileSerializer(user).data)


class CustomerListView(PrivateResponseMixin, generics.ListAPIView):
    permission_classes = [IsAdministrator]
    serializer_class = CustomerSerializer
    queryset = Customer.objects.select_related("user").order_by("id")


class CustomerDetailView(PrivateResponseMixin, generics.RetrieveAPIView):
    permission_classes = [IsAdministrator]
    serializer_class = CustomerSerializer
    queryset = Customer.objects.select_related("user").order_by("id")

    def retrieve(self, request, *args, **kwargs):
        return Response(CustomerSerializer(self.get_object()).data)

    @extend_schema(request=CustomerUpdateSerializer, responses=CustomerSerializer)
    def patch(self, request, *args, **kwargs):
        serializer = CustomerUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = self.get_object()
        user = service_call(
            manage_customer,
            actor=request.user,
            customer=customer,
            **serializer.validated_data,
        )
        customer.refresh_from_db()
        customer.user = user
        return Response(CustomerSerializer(customer).data)

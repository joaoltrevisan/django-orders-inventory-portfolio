from django.utils.crypto import constant_time_compare
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password

from common.api import service_call
from common.serializers import JSONBooleanField, StrictInputMixin, TextField

from .authentication import token_user_id
from .models import Customer, User
from .services import register_customer


class ProfileSerializer(serializers.ModelSerializer):
    data_origin = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "name", "phone", "role", "is_active", "data_origin"]
        read_only_fields = fields

    def get_data_origin(self, user) -> str:
        return "SIMULATED_API"

    def get_phone(self, user) -> str | None:
        try:
            return user.customer.phone
        except Customer.DoesNotExist:
            return None

    def get_role(self, user) -> str:
        return "administrator" if user.is_staff else "customer"


class RegistrationSerializer(StrictInputMixin, serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    name = TextField(max_length=150)
    password = TextField(write_only=True, trim_whitespace=False, max_length=128)
    phone = TextField(max_length=20, allow_blank=True, required=False)

    def create(self, validated_data):
        return service_call(register_customer, **validated_data)


class CustomerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    name = serializers.CharField(source="user.name", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    data_origin = serializers.CharField(default="SIMULATED_API", read_only=True)

    class Meta:
        model = Customer
        fields = ["id", "user_id", "email", "name", "phone", "is_active", "data_origin"]
        read_only_fields = fields


class ProfileUpdateSerializer(StrictInputMixin, serializers.Serializer):
    name = TextField(max_length=150, required=False)
    phone = TextField(max_length=20, allow_blank=True, required=False)


class CustomerUpdateSerializer(ProfileUpdateSerializer):
    is_active = JSONBooleanField(required=False)


class LoginSerializer(StrictInputMixin, TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"] = serializers.EmailField(max_length=254, write_only=True)
        self.fields["password"] = TextField(write_only=True, trim_whitespace=False, max_length=128)


class ActiveUserRefreshSerializer(StrictInputMixin, TokenRefreshSerializer):
    refresh = TextField(write_only=True, max_length=4096, trim_whitespace=False)

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        try:
            user = User.objects.get(pk=token_user_id(refresh))
        except User.DoesNotExist as error:
            raise AuthenticationFailed("Invalid credentials.") from error
        # Preserve signature, expiry and token-type checks, then check current account state.
        if not api_settings.USER_AUTHENTICATION_RULE(user) or not constant_time_compare(
            str(refresh.get(api_settings.REVOKE_TOKEN_CLAIM, "")),
            get_md5_hash_password(user.password),
        ):
            raise AuthenticationFailed("Invalid credentials.")
        return {"access": str(refresh.access_token)}

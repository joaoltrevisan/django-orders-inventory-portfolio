from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings


def token_user_id(token):
    value = token.get(api_settings.USER_ID_CLAIM)
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdecimal()
        or len(value) > 19
        or not 0 < int(value) <= 9223372036854775807
    ):
        raise InvalidToken("Invalid user identity.")
    return value


class DatabaseJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        token_user_id(validated_token)
        return super().get_user(validated_token)

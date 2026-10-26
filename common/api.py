from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError


def service_call(function, **kwargs):
    try:
        return function(**kwargs)
    except DjangoValidationError as error:
        detail = error.message_dict if hasattr(error, "message_dict") else error.messages
        raise ValidationError(detail) from error


class PrivateResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

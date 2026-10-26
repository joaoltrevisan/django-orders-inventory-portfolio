from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .models import User


def is_administrator(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_staff)


def require_administrator(user):
    if (
        not isinstance(user, User)
        or not user.pk
        or not User.objects.filter(pk=user.pk, is_active=True, is_staff=True).exists()
    ):
        raise PermissionDenied("Administrator access is required.")


class IsAdministrator(BasePermission):
    message = "Administrator access is required."

    def has_permission(self, request, view):
        return is_administrator(request.user)

from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .models import Customer, User


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


def require_customer(user):
    customer = None
    if isinstance(user, User) and user.pk:
        customer = Customer.objects.filter(
            user_id=user.pk, user__is_active=True, user__is_staff=False
        ).first()
    if customer is None:
        raise PermissionDenied("An active customer account is required.")
    return customer


class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and not user.is_staff
            and Customer.objects.filter(user_id=user.pk).exists()
        )


class CanAccessOrder(BasePermission):
    def has_permission(self, request, view):
        return is_administrator(request.user) or IsCustomer().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        return is_administrator(request.user) or obj.customer.user_id == request.user.pk

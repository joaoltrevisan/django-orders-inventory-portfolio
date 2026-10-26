"""Account writes adapted from the existing API, with locked profile updates."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from .models import Customer, User
from .permissions import require_administrator


def email_conflict(error):
    if getattr(error.__cause__, "sqlstate", None) == "23505" and (
        error.__cause__.diag.constraint_name in {"user_email_ci_unique", "accounts_user_email_key"}
    ):
        raise ValidationError({"email": ["Email is already registered."]}) from error
    raise error


def register_customer(*, email, name, password, phone=""):
    candidate = User(email=User.objects.normalize_email(email), name=name)
    try:
        validate_password(password, user=candidate)
    except ValidationError as error:
        raise ValidationError({"password": error.messages}) from error
    try:
        with transaction.atomic():
            user = User.objects.create_user(candidate.email, password, name=name)
            customer = Customer(user=user, phone=phone)
            customer.full_clean()
            customer.save()
            return user
    except IntegrityError as error:
        email_conflict(error)


def update_profile(*, user, name=None, phone=None):
    if not isinstance(user, User) or not user.pk:
        raise PermissionDenied("An active account is required.")
    with transaction.atomic():
        current = User.objects.select_for_update().get(pk=user.pk)
        if not current.is_active:
            raise PermissionDenied("An active account is required.")
        return _update_locked_profile(current, name=name, phone=phone)


def _update_locked_profile(current, *, name=None, phone=None):
    if name is not None:
        current.name = name
        current.full_clean()
        current.save(update_fields=["name"])
    if phone is not None:
        try:
            customer = current.customer
        except Customer.DoesNotExist as error:
            raise ValidationError({"phone": ["This account has no customer profile."]}) from error
        customer.phone = phone
        customer.full_clean()
        customer.save(update_fields=["phone", "updated_at"])
    return current


def manage_customer(*, actor, customer, name=None, phone=None, is_active=None):
    require_administrator(actor)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=customer.user_id)
        user = _update_locked_profile(user, name=name, phone=phone)
        if is_active is not None:
            user.is_active = is_active
            user.save(update_fields=["is_active"])
        return user

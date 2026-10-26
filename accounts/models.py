from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower, Trim
from django.utils import timezone

from common.models import TimestampedModel

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="user_email_ci_unique"),
            models.CheckConstraint(
                condition=models.Q(email=Trim("email")) & models.Q(email__regex=r"\S"),
                name="user_email_not_blank_or_padded",
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=r"\S"), name="user_name_required"
            ),
        ]

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name.split()[0] if self.name.split() else ""

    def __str__(self):
        return self.email


class Customer(TimestampedModel):
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="customer")
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"Customer {self.pk}"

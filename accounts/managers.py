from django.contrib.auth.base_user import BaseUserManager
from django.db.models import Value
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        return super().normalize_email(email).strip().lower()

    def get_by_natural_key(self, username):
        # Match the same LOWER equivalence used by the unique email constraint.
        return self.alias(email_key=Lower("email")).get(
            email_key=Lower(Value(self.normalize_email(username)))
        )

    def create_user(self, email, password=None, **extra_fields):
        if not email or not email.strip():
            raise ValueError("Email is required.")
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True or extra_fields["is_superuser"] is not True:
            raise ValueError("A superuser requires is_staff=True and is_superuser=True.")
        return self.create_user(email, password, **extra_fields)

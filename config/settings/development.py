import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if len(SECRET_KEY) < 48:
    raise ImproperlyConfigured(
        "Set DJANGO_SECRET_KEY to a generated secret of at least 48 characters."
    )

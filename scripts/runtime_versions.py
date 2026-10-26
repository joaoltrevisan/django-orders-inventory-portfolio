"""Print runtime/version metadata only; never configuration secrets."""

import importlib.metadata
import json
import os
import platform

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.db import connection  # noqa: E402

with connection.cursor() as cursor:
    cursor.execute("SELECT version(), current_user, current_setting('TimeZone')")
    postgresql, database_role, database_timezone = cursor.fetchone()

print(
    json.dumps(
        {
            "python": platform.python_version(),
            "architecture": platform.machine(),
            "postgresql": postgresql,
            "database_role": database_role,
            "database_timezone": database_timezone,
            "packages": {
                name: importlib.metadata.version(name)
                for name in [
                    "Django",
                    "djangorestframework",
                    "djangorestframework-simplejwt",
                    "psycopg",
                    "PyJWT",
                    "drf-spectacular",
                    "ruff",
                ]
            },
        },
        indent=2,
    )
)

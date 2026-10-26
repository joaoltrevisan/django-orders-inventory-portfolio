"""Source clocks are calendar values with no verified time zone."""

import re
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import NotSupportedError, models


class SourceDateTimeField(models.Field):
    """Use native timezone-free timestamps without Django's aware conversions.

    Intentionally not a DateTimeField: Django's date transforms/truncations can
    inject AT TIME ZONE under USE_TZ. Source reports must use explicit verified
    timezone-free SQL expressions. Exact/range comparisons and ordering work.
    """

    description = "Source timestamp without a verified time zone"

    def db_type(self, connection):
        if connection.vendor != "postgresql":
            raise NotSupportedError("Source timestamps require PostgreSQL.")
        return "timestamp without time zone"

    def to_python(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value):
                    raise ValueError
                value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError as error:
                raise ValidationError("Enter a source timestamp as YYYY-MM-DD HH:MM:SS.") from error
        if not isinstance(value, datetime) or value.utcoffset() is not None:
            raise ValidationError("Source timestamps must be timezone-free datetime values.")
        if value.microsecond:
            raise ValidationError("Source timestamps must have whole-second precision.")
        return value

    def get_prep_value(self, value):
        return self.to_python(value)

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return value.strftime("%Y-%m-%d %H:%M:%S") if value is not None else None

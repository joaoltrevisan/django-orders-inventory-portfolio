import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class StrictIntegerField(models.IntegerField):
    """Reject silent ORM conversion of fractional quantities and booleans."""

    def to_python(self, value):
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValidationError("Enter an integer quantity, not a boolean.")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value):
            return int(value)
        if isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
            return int(value)
        raise ValidationError("Enter an integer quantity without a fractional part.")

    def get_prep_value(self, value):
        return self.to_python(value)

from django.core.exceptions import ValidationError
from django.http import Http404

MAX_ID = 9223372036854775807


def validate_id(value):
    if type(value) is not int or not 1 <= value <= MAX_ID:
        raise Http404("Resource not found.")
    return value


def clean_text(value, field, *, max_length, blank=False):
    if not isinstance(value, str):
        raise ValidationError({field: ["Enter text."]})
    value = value.strip()
    if (not blank and not value) or len(value) > max_length or "\x00" in value:
        raise ValidationError({field: [f"Enter valid text with at most {max_length} characters."]})
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValidationError({field: ["Enter valid Unicode text."]}) from error
    return value

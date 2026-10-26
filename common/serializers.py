"""Strict JSON boundaries shared by the operational endpoints."""

from collections.abc import Mapping

from rest_framework import serializers


class StrictInputMixin:
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            writable = {key for key, field in self.fields.items() if not field.read_only}
            forbidden = data.keys() - writable
            if forbidden:
                raise serializers.ValidationError(
                    dict.fromkeys(sorted(forbidden), ["Field is not permitted."])
                )
        return super().to_internal_value(data)


class TextField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        if "\x00" in data:
            raise serializers.ValidationError("Null characters are not permitted.")
        try:
            data.encode("utf-8")
        except UnicodeEncodeError as error:
            raise serializers.ValidationError("Enter valid Unicode text.") from error
        return super().to_internal_value(data)


class JSONBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            raise serializers.ValidationError("Enter a JSON boolean.")
        return super().to_internal_value(data)


class MoneyInputField(serializers.DecimalField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("Enter money as a decimal string, such as 25.90.")
        return super().to_internal_value(data)

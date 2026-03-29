from ipaddress import _BaseNetwork, ip_network

from django import forms
from django.core.exceptions import ValidationError
from django.db import models


class IpNetworkFormField(forms.Field):
    widget = forms.TextInput
    default_error_messages = {
        "invalid": "Enter a valid CIDR address.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if not value:
            return None

        if isinstance(value, _BaseNetwork):
            network = value

        if isinstance(value, str):
            value = value.strip()

        try:
            network = ip_network(value, strict=False)
        except ValueError:
            raise ValidationError(self.default_error_messages["invalid"])
        return network


class NetworkField(models.Field):
    empty_strings_allowed = False
    description = "CIDR type network field"

    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 43
        super().__init__(*args, **kwargs)

    def db_type(self, connection):
        return "cidr"

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        if not value:
            return value
        try:
            return ip_network(value, strict=False)
        except ValueError as e:
            raise ValidationError(e)

    def get_prep_value(self, value):
        if value is None:
            return None
        return str(self.to_python(value))

    def formfield(self, **kwargs):
        defaults = {"form_class": IpNetworkFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.max_length is not None:
            kwargs["max_length"] = self.max_length
        return name, path, args, kwargs

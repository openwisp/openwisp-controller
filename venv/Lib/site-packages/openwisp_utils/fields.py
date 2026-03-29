from django import forms
from django.db.models.fields import (
    BLANK_CHOICE_DASH,
    BooleanField,
    CharField,
    DecimalField,
    PositiveIntegerField,
    TextField,
    URLField,
)
from django.utils.translation import gettext_lazy as _
from openwisp_utils.utils import get_random_key
from openwisp_utils.validators import key_validator


class KeyField(CharField):
    default_callable = get_random_key
    default_validators = [key_validator]

    def __init__(
        self,
        max_length: int = 64,
        unique: bool = False,
        db_index: bool = False,
        help_text: str = None,
        default: [str, callable, None] = default_callable,
        validators: list = default_validators,
        *args,
        **kwargs,
    ):
        super().__init__(
            max_length=max_length,
            unique=unique,
            db_index=db_index,
            help_text=help_text,
            default=default,
            validators=validators,
            *args,
            **kwargs,
        )


class FallbackMixin(object):
    """Returns the fallback value when the value of the field is falsy (None or '').

    If the value of the field is equal to the fallback value, then the
    field will save `None` in the database.
    """

    def __init__(self, *args, **kwargs):
        self.fallback = kwargs.pop("fallback")
        opts = dict(blank=True, null=True, default=None)
        opts.update(kwargs)
        super().__init__(*args, **opts)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["fallback"] = self.fallback
        return (name, path, args, kwargs)

    def from_db_value(self, value, expression, connection):
        """Called when fetching value from the database."""
        if value is None:
            return self.fallback
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        """Called when saving value in the database."""
        value = super().get_db_prep_value(value, connection, prepared)
        if value == self.fallback:
            return None
        return value

    def get_default(self):
        """Returns the fallback value for the default.

        The default is set to `None` on field initialization to ensure
        that the default value in the database schema is `NULL` instead of
        a non-null value (fallback value). Returning the fallback value
        here also sets the initial value of the field to the fallback
        value in admin add forms, similar to how Django handles default
        values.
        """
        return self.fallback


class FalsyValueNoneMixin:
    """Stores None instead of empty strings.

    If the field contains an empty string and the field can be NULL, this
    mixin will prefer to store "None" in the database.
    """

    # Django convention is to use the empty string, not NULL
    # for representing "no data" in the database.
    # https://docs.djangoproject.com/en/dev/ref/models/fields/#null
    # We need to use NULL for fallback field here to keep
    # the fallback logic simple. Hence, we allow only "None" (NULL)
    # as empty value here.
    empty_values = [None]

    def clean(self, value, model_instance):
        if not value and self.null is True:
            return None
        return super().clean(value, model_instance)


class FallbackBooleanChoiceField(FallbackMixin, BooleanField):
    def formfield(self, **kwargs):
        kwargs.update(
            {
                "form_class": forms.BooleanField,
                "widget": forms.Select(
                    choices=BLANK_CHOICE_DASH
                    + [
                        (True, _("Enabled")),
                        (False, _("Disabled")),
                    ]
                ),
            }
        )
        return super().formfield(**kwargs)


class FallbackCharChoiceField(FallbackMixin, CharField):
    def formfield(self, **kwargs):
        kwargs.update(
            {
                "choices_form_class": forms.TypedChoiceField,
            }
        )
        return super().formfield(**kwargs)


class FallbackPositiveIntegerField(FallbackMixin, PositiveIntegerField):
    pass


class FallbackCharField(FallbackMixin, FalsyValueNoneMixin, CharField):
    """Populates the form with the fallback value if the value is set to null in the database."""

    pass


class FallbackURLField(FallbackMixin, FalsyValueNoneMixin, URLField):
    """Populates the form with the fallback value if the value is set to null in the database."""

    pass


class FallbackTextField(FallbackMixin, FalsyValueNoneMixin, TextField):
    """Populates the form with the fallback value if the value is set to null in the database."""

    def formfield(self, **kwargs):
        kwargs.update(
            {
                "form_class": forms.CharField,
                "widget": forms.Textarea(
                    attrs={"rows": 2, "cols": 34, "style": "width:auto"}
                ),
            }
        )
        return super().formfield(**kwargs)


class FallbackDecimalField(FallbackMixin, DecimalField):
    pass

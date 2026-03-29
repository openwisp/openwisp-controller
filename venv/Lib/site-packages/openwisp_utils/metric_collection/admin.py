from django import forms
from django.forms.utils import ErrorList

from .models import Consent


class ConsentForm(forms.ModelForm):
    # This required to override the default label_suffix.
    # Otherwise, it will show a trailing colon (:) which we
    # don't want here due to formatting of the form.
    def __init__(
        self,
        data=None,
        files=None,
        auto_id="id_%s",
        prefix=None,
        initial=None,
        error_class=ErrorList,
        label_suffix="",
        empty_permitted=False,
        instance=None,
        use_required_attribute=None,
        renderer=None,
    ):
        super().__init__(
            data,
            files,
            auto_id,
            prefix,
            initial,
            error_class,
            label_suffix,
            empty_permitted,
            instance,
            use_required_attribute,
            renderer,
        )

    class Meta:
        model = Consent
        widgets = {"user_consented": forms.CheckboxInput(attrs={"class": "bold"})}
        fields = ["user_consented"]

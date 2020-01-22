from django import forms

from openwisp_users.models import Organization


class CloneOrganizationForm(forms.Form):
    organization = forms.ModelChoiceField(queryset=Organization.objects.none())

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop('queryset')
        super().__init__(*args, **kwargs)
        self.fields['organization'].queryset = queryset

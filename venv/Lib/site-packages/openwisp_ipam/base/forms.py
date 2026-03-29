from django import forms


class IpAddressImportForm(forms.Form):
    csvfile = forms.FileField(label="CSV File")

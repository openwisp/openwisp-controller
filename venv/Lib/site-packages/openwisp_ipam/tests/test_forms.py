from ipaddress import ip_network

from django.forms import ModelForm
from django.test import TestCase
from swapper import load_model

Subnet = load_model("openwisp_ipam", "Subnet")


class NetworkAddressTestModelForm(ModelForm):
    class Meta:
        model = Subnet
        fields = ("subnet",)


class TestForms(TestCase):
    form_class = NetworkAddressTestModelForm

    def test_none_value(self):
        form = self.form_class({"subnet": None})
        self.assertFalse(form.is_valid())

    def test_field_base_network_value(self):
        form = self.form_class({"subnet": ip_network(b"\xc0\xa8\x00\x01")})
        self.assertTrue(form.is_valid())

    def test_form_ipv4_valid(self):
        form = self.form_class({"subnet": "10.0.1.0/24"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["subnet"], ip_network("10.0.1.0/24"))

    def test_form_ipv4_invalid(self):
        form = self.form_class({"subnet": "10.0.0.1.2/32"})
        self.assertFalse(form.is_valid())

    def test_form_ipv4_strip(self):
        form = self.form_class({"subnet": " 10.0.1.0/24 "})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["subnet"], ip_network("10.0.1.0/24"))

    def test_form_ipv6_valid(self):
        form = self.form_class({"subnet": "2001:0:1::/64"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["subnet"], ip_network("2001:0:1::/64"))

    def test_form_ipv6_invalid(self):
        form = self.form_class({"subnet": "2001:0::1::2/128"})
        self.assertFalse(form.is_valid())

    def test_form_ipv6_strip(self):
        form = self.form_class({"subnet": " 2001:0:1::/64 "})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["subnet"], ip_network("2001:0:1::/64"))

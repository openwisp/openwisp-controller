from django.test import TestCase

from django_x509.tests import TestX509Mixin
from django_x509.tests.test_admin import ModelAdminTests as BaseModelAdminTests
from django_x509.tests.test_ca import TestCa as BaseTestCa
from django_x509.tests.test_cert import TestCert as BaseTestCert

from .models import CustomCert


class TestCustomCert(TestX509Mixin, TestCase):
    def test_pk_field(self):
        """Test that a cert can be created without an AttributeError."""
        cert = self._create_cert(cert_model=CustomCert, fingerprint="123")
        self.assertEqual(cert.pk, cert.fingerprint)


class ModelAdminTests(BaseModelAdminTests):
    app_label = "sample_x509"


class TestCert(BaseTestCert):
    pass


class TestCa(BaseTestCa):
    pass


del BaseModelAdminTests
del BaseTestCa
del BaseTestCert

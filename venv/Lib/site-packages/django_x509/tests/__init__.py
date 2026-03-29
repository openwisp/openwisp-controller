from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpRequest
from swapper import load_model

Ca = load_model("django_x509", "Ca")
Cert = load_model("django_x509", "Cert")

GENERALIZED_TIME = "%Y%m%d%H%M%SZ"
UTC_TIME = "%y%m%d%H%M%SZ"


def datetime_to_string(datetime_):
    """
    Helper to convert datetime to the string format used in certificates.
    Centralized here to avoid duplication across test files.
    """
    return datetime_.strftime(UTC_TIME)


class MessagingRequest(HttpRequest):
    session = "session"

    def __init__(self):
        super().__init__()
        self._messages = FallbackStorage(self)

    def get_messages(self):
        return getattr(self._messages, "_queued_messages")

    def get_message_strings(self):
        return [str(m) for m in self.get_messages()]


class TestX509Mixin(object):
    def _create_ca(self, **kwargs):
        options = dict(
            name="Test CA",
            key_length="2048",
            digest="sha256",
            country_code="IT",
            state="RM",
            city="Rome",
            organization_name="OpenWISP",
            email="test@test.com",
            common_name="openwisp.org",
            extensions=[],
        )
        options.update(kwargs)
        ca = Ca(**options)
        ca.full_clean()
        ca.save()
        return ca

    def _create_cert(self, cert_model=None, **kwargs):
        if not cert_model:
            cert_model = Cert
        options = dict(
            name="TestCert",
            ca=None,
            key_length="2048",
            digest="sha256",
            country_code="IT",
            state="RM",
            city="Rome",
            organization_name="Test",
            email="test@test.com",
            common_name="openwisp.org",
            extensions=[],
        )
        options.update(kwargs)
        # auto create CA if not supplied
        if not options.get("ca"):
            options["ca"] = self._create_ca()
        cert = cert_model(**options)
        cert.full_clean()
        cert.save()
        return cert

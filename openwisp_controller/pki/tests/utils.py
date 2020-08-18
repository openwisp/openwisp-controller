from django_x509.tests import TestX509Mixin
from swapper import load_model


class TestPkiMixin(TestX509Mixin):
    ca_model = load_model('django_x509', 'Ca')
    cert_model = load_model('django_x509', 'Cert')

    def _create_ca(self, **kwargs):
        if 'organization' not in kwargs:
            kwargs['organization'] = None
        return super()._create_ca(**kwargs)

    def _create_cert(self, **kwargs):
        if 'organization' not in kwargs:
            kwargs['organization'] = None
        return super()._create_cert(**kwargs)

from django_x509.tests import TestX509Mixin


class TestPkiMixin(TestX509Mixin):
    def _create_ca(self, **kwargs):
        if 'organization' not in kwargs:
            kwargs['organization'] = None
        return super()._create_ca(**kwargs)

    def _create_cert(self, **kwargs):
        if 'organization' not in kwargs:
            kwargs['organization'] = None
        return super()._create_cert(**kwargs)

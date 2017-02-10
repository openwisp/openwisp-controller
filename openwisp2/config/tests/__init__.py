from django.contrib.auth import get_user_model
from django_netjsonconfig.tests import (CreateConfigMixin,
                                        CreateTemplateMixin,
                                        CreateVpnMixin)
from ...pki.tests import TestPkiMixin


class TestVpnX509Mixin(CreateVpnMixin, TestPkiMixin):
    pass


class CreateConfigTemplateMixin(CreateTemplateMixin, CreateConfigMixin):
    pass


class CreateAdminMixin(object):
    def setUp(self):
        user_model = get_user_model()
        user_model.objects.create_superuser(username='admin',
                                            password='tester',
                                            email='admin@admin.com')

    def _login(self, username='admin', password='tester'):
        self.client.login(username=username, password=password)

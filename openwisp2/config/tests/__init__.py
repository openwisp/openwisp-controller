from django.contrib.auth import get_user_model
from django_netjsonconfig.tests import (CreateConfigMixin,
                                        CreateTemplateMixin,
                                        CreateVpnMixin)
from ...pki.tests import TestPkiMixin


class TestVpnX509Mixin(CreateVpnMixin, TestPkiMixin):
    def _create_vpn(self, ca_options={}, **kwargs):
        if 'ca' not in kwargs:
            org = kwargs.get('organization')
            name = org.name if org else kwargs.get('name') or 'test'
            ca_options['name'] = '{0}-ca'.format(name)
            ca_options['organization'] = org
        return super(TestVpnX509Mixin, self)._create_vpn(ca_options, **kwargs)


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

    def _logout(self):
        self.client.logout()

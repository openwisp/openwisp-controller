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
    def _create_config(self, **kwargs):
        if 'device' not in kwargs:
            kwargs['device'] = self._create_device(name='test-device',
                                                   organization=kwargs.get('organization', None))
        if 'organization' not in kwargs:
            kwargs['organization'] = kwargs['device'].organization
        return super(CreateConfigTemplateMixin, self)._create_config(**kwargs)

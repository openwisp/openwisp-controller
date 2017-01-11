from django_netjsonconfig.tests import CreateVpnMixin
from ...pki.tests import TestPkiMixin


class TestVpnX509Mixin(CreateVpnMixin, TestPkiMixin):
    pass


class CreateConfigMixin(object):
    TEST_KEY = 'w1gwJxKaHcamUw62TQIPgYchwLKn3AA0'
    TEST_MAC_ADDRESS = '00:11:22:33:44:55'

    def _create_config(self, **kwargs):
        options = dict(name='test',
                       organization=None,
                       mac_address=self.TEST_MAC_ADDRESS,
                       backend='netjsonconfig.OpenWrt',
                       config={'general': {'hostname': 'test-config'}},
                       key=self.TEST_KEY)
        options.update(kwargs)
        c = self.config_model(**options)
        c.full_clean()
        c.save()
        return c

"""
test utilities shared among test classes
these mixins are reused also in openwisp2
change with care.
"""
from uuid import uuid4

from ...pki.tests.utils import TestPkiMixin


class CreateDeviceMixin(object):
    TEST_MAC_ADDRESS = '00:11:22:33:44:55'

    def _create_device(self, **kwargs):
        options = dict(
            name='default.test.device',
            organization=self._get_org(),
            mac_address=self.TEST_MAC_ADDRESS,
            hardware_id=str(uuid4().hex),
            model='TP-Link TL-WDR4300 v1',
            os='LEDE Reboot 17.01-SNAPSHOT r3313-c2999ef',
        )
        options.update(kwargs)
        d = self.device_model(**options)
        d.full_clean()
        d.save()
        return d

    def _create_device_config(self, device_opts=None, config_opts=None):
        device_opts = device_opts or {}
        config_opts = config_opts or {}
        device_opts['name'] = 'test'
        d = self._create_device(**device_opts)
        config_opts['device'] = d
        self._create_config(**config_opts)
        return d


class CreateConfigMixin(CreateDeviceMixin):
    TEST_KEY = 'w1gwJxKaHcamUw62TQIPgYchwLKn3AA0'

    def _create_config(self, **kwargs):
        options = dict(backend='netjsonconfig.OpenWrt', config={'general': {}})
        options.update(kwargs)
        if 'device' not in kwargs:
            options['device'] = self._create_device(
                organization=self._get_org(), name='test-device'
            )
        c = self.config_model(**options)
        c.full_clean()
        c.save()
        return c


class CreateTemplateMixin(object):
    def _create_template(self, **kwargs):
        model_kwargs = {
            'name': 'test-template',
            'backend': 'netjsonconfig.OpenWrt',
            'config': {'interfaces': [{'name': 'eth0', 'type': 'ethernet'}]},
        }
        model_kwargs.update(kwargs)
        t = self.template_model(**model_kwargs)
        t.full_clean()
        t.save()
        return t


class CreateVpnMixin(object):
    _dh = """-----BEGIN DH PARAMETERS-----
MIGHAoGBAMkiqC2kAkjhysnuBORxJgDMdq3JrvaNh1kZW0IkFiyLRyhtYf92atP4
ycYELVoRZoRZ8zp2Y2L71vHRNx5okiXZ1xRWDfEVp7TFVc+oCTTRwJqyq21/DJpe
Qt01H2yL7CvdEUi/gCUJNS9Jm40248nwKgyrwyoS3SjY49CAcEYLAgEC
-----END DH PARAMETERS-----"""
    _vpn_config = {
        'openvpn': [
            {
                'ca': 'ca.pem',
                'cert': 'cert.pem',
                'dev': 'tap0',
                'dev_type': 'tap',
                'dh': 'dh.pem',
                'key': 'key.pem',
                'mode': 'server',
                'name': 'example-vpn',
                'proto': 'udp',
                'tls_server': True,
            }
        ]
    }

    def _create_vpn(self, ca_options={}, **kwargs):
        options = dict(
            name='test',
            host='vpn1.test.com',
            ca=None,
            backend='openwisp_controller.vpn_backends.OpenVpn',
            config=self._vpn_config,
            dh=self._dh,
        )
        options.update(**kwargs)
        if not options['ca']:
            options['ca'] = self._create_ca(**ca_options)
        vpn = self.vpn_model(**options)
        vpn.full_clean()
        vpn.save()
        return vpn


class TestVpnX509Mixin(CreateVpnMixin, TestPkiMixin):
    def _create_vpn(self, ca_options={}, **kwargs):
        if 'ca' not in kwargs:
            org = kwargs.get('organization')
            name = org.name if org else kwargs.get('name') or 'test'
            ca_options['name'] = '{0}-ca'.format(name)
            ca_options['organization'] = org
        return super()._create_vpn(ca_options, **kwargs)


class CreateConfigTemplateMixin(CreateTemplateMixin, CreateConfigMixin):
    def _create_config(self, **kwargs):
        if 'device' not in kwargs:
            kwargs['device'] = self._create_device(
                name='test-device', organization=kwargs.pop('organization')
            )
        return super()._create_config(**kwargs)

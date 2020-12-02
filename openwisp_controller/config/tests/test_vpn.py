from unittest import mock

from celery.exceptions import SoftTimeLimitExceeded
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from ...vpn_backends import OpenVpn
from .. import settings as app_settings
from ..tasks import create_vpn_dh
from .utils import CreateConfigTemplateMixin, TestVpnX509Mixin

Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
VpnClient = load_model('config', 'VpnClient')
Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')


class TestVpn(
    TestOrganizationMixin, TestVpnX509Mixin, CreateConfigTemplateMixin, TestCase
):
    """
    tests for Vpn model
    """

    maxDiff = None

    def test_config_not_none(self):
        v = Vpn(
            name='test',
            host='vpn1.test.com',
            ca=self._create_ca(),
            backend='openwisp_controller.vpn_backends.OpenVpn',
            config=None,
            dh=self._dh,
        )
        try:
            v.full_clean()
        except ValidationError:
            pass
        self.assertEqual(v.config, {})

    def test_backend_class(self):
        v = Vpn(
            name='test',
            host='vpn1.test.com',
            ca=self._create_ca(),
            backend='openwisp_controller.vpn_backends.OpenVpn',
        )
        self.assertIs(v.backend_class, OpenVpn)

    def test_backend_instance(self):
        v = Vpn(
            name='test',
            host='vpn1.test.com',
            ca=self._create_ca(),
            backend='openwisp_controller.vpn_backends.OpenVpn',
            config={},
        )
        self.assertIsInstance(v.backend_instance, OpenVpn)

    def test_validation(self):
        config = {'openvpn': {'invalid': True}}
        v = Vpn(
            name='test',
            host='vpn1.test.com',
            ca=self._create_ca(),
            backend='openwisp_controller.vpn_backends.OpenVpn',
            config=config,
        )
        # ensure django ValidationError is raised
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_json(self):
        v = self._create_vpn()
        self.assertDictEqual(v.json(dict=True), self._vpn_config)

    def test_automatic_cert_creation(self):
        vpn = self._create_vpn()
        self.assertIsNotNone(vpn.cert)
        server_extensions = [
            {'name': 'nsCertType', 'value': 'server', 'critical': False}
        ]
        self.assertEqual(vpn.cert.extensions, server_extensions)

    def test_vpn_client_unique_together(self):
        org = self._get_org()
        vpn = self._create_vpn()
        t = self._create_template(name='vpn-test', type='vpn', vpn=vpn)
        c = self._create_config(organization=org)
        c.templates.add(t)
        # one VpnClient instance has been automatically created
        # now try to create a duplicate
        client = VpnClient(vpn=vpn, config=c, auto_cert=True)
        try:
            client.full_clean()
        except ValidationError as e:
            self.assertIn(
                'with this Config and Vpn already exists', e.message_dict['__all__'][0]
            )
        else:
            self.fail('unique_together clause not triggered')

    def test_vpn_client_auto_cert_deletes_cert(self):
        org = self._get_org()
        vpn = self._create_vpn()
        t = self._create_template(name='vpn-test', type='vpn', vpn=vpn, auto_cert=True)
        c = self._create_config(organization=org)
        c.templates.add(t)
        vpnclient = c.vpnclient_set.first()
        cert_pk = vpnclient.cert.pk
        self.assertEqual(Cert.objects.filter(pk=cert_pk).count(), 1)
        c.delete()
        self.assertEqual(VpnClient.objects.filter(pk=vpnclient.pk).count(), 0)
        self.assertEqual(Cert.objects.filter(pk=cert_pk).count(), 0)

    def test_vpn_cert_and_ca_mismatch(self):
        ca = self._create_ca()
        different_ca = self._create_ca()
        cert = Cert(
            name='test-cert-vpn',
            ca=ca,
            key_length='2048',
            digest='sha256',
            country_code='IT',
            state='RM',
            city='Rome',
            organization_name='OpenWISP',
            email='test@test.com',
            common_name='openwisp.org',
        )
        cert.full_clean()
        cert.save()
        vpn = Vpn(
            name='test',
            host='vpn1.test.com',
            ca=different_ca,
            cert=cert,
            backend='openwisp_controller.vpn_backends.OpenVpn',
        )
        try:
            vpn.full_clean()
        except ValidationError as e:
            self.assertIn('cert', e.message_dict)
        else:
            self.fail('Mismatch between ca and cert but ValidationError not raised')

    def test_auto_client(self):
        vpn = self._create_vpn()
        auto = vpn.auto_client()
        context_keys = vpn._get_auto_context_keys()
        for key in context_keys.keys():
            context_keys[key] = '{{%s}}' % context_keys[key]
        control = vpn.backend_class.auto_client(
            host=vpn.host, server=self._vpn_config['openvpn'][0], **context_keys
        )
        control['files'] = [
            {
                'path': context_keys['ca_path'],
                'mode': '0600',
                'contents': context_keys['ca_contents'],
            },
            {
                'path': context_keys['cert_path'],
                'mode': '0600',
                'contents': context_keys['cert_contents'],
            },
            {
                'path': context_keys['key_path'],
                'mode': '0600',
                'contents': context_keys['key_contents'],
            },
        ]
        self.assertDictEqual(auto, control)

    def test_auto_client_auto_cert_False(self):
        vpn = self._create_vpn()
        auto = vpn.auto_client(auto_cert=False)
        context_keys = vpn._get_auto_context_keys()
        for key in context_keys.keys():
            context_keys[key] = '{{%s}}' % context_keys[key]
        for key in ['cert_path', 'cert_contents', 'key_path', 'key_contents']:
            del context_keys[key]
        control = vpn.backend_class.auto_client(
            host=vpn.host, server=self._vpn_config['openvpn'][0], **context_keys
        )
        control['files'] = [
            {
                'path': context_keys['ca_path'],
                'mode': '0600',
                'contents': context_keys['ca_contents'],
            }
        ]
        self.assertDictEqual(auto, control)

    def test_vpn_client_get_common_name(self):
        vpn = self._create_vpn()
        d = self._create_device()
        c = self._create_config(device=d)
        client = VpnClient(vpn=vpn, config=c, auto_cert=True)
        self.assertEqual(
            client._get_common_name(), '{mac_address}-{name}'.format(**d.__dict__)
        )
        d.name = d.mac_address
        self.assertEqual(client._get_common_name(), d.mac_address)

    def test_get_auto_context_keys(self):
        vpn = self._create_vpn()
        keys = vpn._get_auto_context_keys()
        pk = vpn.pk.hex
        control = {
            'ca_path': 'ca_path_{0}'.format(pk),
            'ca_contents': 'ca_contents_{0}'.format(pk),
            'cert_path': 'cert_path_{0}'.format(pk),
            'cert_contents': 'cert_contents_{0}'.format(pk),
            'key_path': 'key_path_{0}'.format(pk),
            'key_contents': 'key_contents_{0}'.format(pk),
        }
        self.assertEqual(keys, control)

    @mock.patch.dict(app_settings.CONTEXT, {'vpnserver1': 'vpn.testdomain.com'})
    def test_get_context(self):
        v = self._create_vpn()
        expected = {
            'ca': v.ca.certificate,
            'cert': v.cert.certificate,
            'key': v.cert.private_key,
            'dh': v.dh,
        }
        expected.update(app_settings.CONTEXT)
        self.assertEqual(v.get_context(), expected)
        self.assertNotEqual(v.get_context(), app_settings.CONTEXT)

    @mock.patch('openwisp_controller.config.base.vpn.AbstractVpn.dhparam')
    def test_dh(self, mocked_dhparam):
        mocked_dhparam.return_value = self._dh
        v = self._create_vpn()
        v.dh = None
        v.save()
        self.assertIsNotNone(v.dh)
        self.assertNotEqual(v.dh, '')
        self.assertTrue(v.dh.startswith('-----BEGIN DH PARAMETERS-----'))
        self.assertTrue(v.dh.endswith('-----END DH PARAMETERS-----\n'))

    @mock.patch.dict(app_settings.CONTEXT, {'vpnserver1': 'vpn.testdomain.com'})
    def test_get_context_empty_vpn(self):
        v = Vpn()
        self.assertEqual(v.get_context(), app_settings.CONTEXT)

    def test_key_validator(self):
        v = self._create_vpn()
        v.key = 'key/key'
        with self.assertRaises(ValidationError):
            v.full_clean()
        v.key = 'key.key'
        with self.assertRaises(ValidationError):
            v.full_clean()
        v.key = 'key key'
        with self.assertRaises(ValidationError):
            v.full_clean()
        v.key = self.TEST_KEY
        v.full_clean()

    def test_vpn_with_org(self):
        org = self._get_org()
        vpn = self._create_vpn(organization=org)
        self.assertEqual(vpn.organization_id, org.pk)

    def test_vpn_without_org(self):
        vpn = self._create_vpn()
        self.assertIsNone(vpn.organization)

    def test_vpn_with_shared_ca(self):
        ca = self._create_ca()  # shared CA
        org = self._get_org()
        vpn = self._create_vpn(organization=org, ca=ca)
        self.assertIsNone(ca.organization)
        self.assertEqual(vpn.ca_id, ca.pk)

    def test_vpn_and_ca_different_organization(self):
        org1 = self._get_org()
        ca = self._create_ca(organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        try:
            self._create_vpn(ca=ca, organization=org2)
        except ValidationError as e:
            self.assertIn('organization', e.message_dict)
            self.assertIn('related CA match', e.message_dict['organization'][0])
        else:
            self.fail('ValidationError not raised')

    def test_vpn_and_cert_different_organization(self):
        org1 = self._get_org()
        # shared CA
        ca = self._create_ca()
        # org1 specific cert
        cert = self._create_cert(ca=ca, organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        try:
            self._create_vpn(ca=ca, cert=cert, organization=org2)
        except ValidationError as e:
            self.assertIn('organization', e.message_dict)
            self.assertIn(
                'related certificate match', e.message_dict['organization'][0]
            )
        else:
            self.fail('ValidationError not raised')

    def test_auto_create_cert_with_long_device_name(self):
        device_name = 'abcdifghijklmnopqrstuvwxyz12345678901234567890'
        org = self._create_org(name='org1')
        vpn = self._create_vpn(organization=org)
        d = self._create_device(organization=org, name=device_name)
        c = self._create_config(device=d)
        client = VpnClient(vpn=vpn, config=c, auto_cert=True)
        client.full_clean()
        client.save()
        self.assertEqual(
            client._get_common_name(), '{mac_address}-{name}'.format(**d.__dict__)
        )
        self.assertEqual(len(client._get_common_name()), 64)
        cert = Cert.objects.filter(organization=org, name=device_name)
        self.assertEqual(cert.count(), 1)
        self.assertEqual(cert.first().common_name, client._get_common_name())

    @mock.patch.object(Vpn, 'dhparam', side_effect=SoftTimeLimitExceeded)
    def test_update_vpn_dh_timeout(self, dhparam):
        vpn = self._create_vpn(dh='')
        with mock.patch('logging.Logger.error') as mocked_logger:
            create_vpn_dh.delay(vpn.pk)
            mocked_logger.assert_called_once()
        dhparam.assert_called_once()

    def test_vpn_get_system_context(self):
        vpn = self._create_vpn()
        self.assertEqual(vpn.get_system_context(), vpn.get_context())


class TestVpnTransaction(
    TestOrganizationMixin,
    TestVpnX509Mixin,
    CreateConfigTemplateMixin,
    TransactionTestCase,
):
    @mock.patch.object(create_vpn_dh, 'delay')
    def test_create_vpn_dh_with_vpn_create(self, delay):
        vpn = self._create_vpn(dh='')
        delay.assert_called_once_with(vpn.pk)

    @mock.patch.object(create_vpn_dh, 'delay')
    def test_placeholder_dh_set(self, delay):
        self._create_vpn(dh='', host='localhost')
        vpn = Vpn.objects.get(host='localhost')
        self.assertEqual(vpn.dh, Vpn._placeholder_dh)
        delay.assert_called_once_with(vpn.pk)

    @mock.patch.object(Vpn, 'dhparam')
    def test_update_vpn_dh(self, dhparam):
        dhparam.return_value = self._dh
        vpn = self._create_vpn(dh='')
        vpn.refresh_from_db()
        self.assertNotEqual(vpn.dh, Vpn._placeholder_dh)
        dhparam.assert_called_once()

import json
from subprocess import CalledProcessError, TimeoutExpired
from unittest import mock

from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.db.utils import IntegrityError
from django.http.response import HttpResponse, HttpResponseNotFound
from django.test import TestCase, TransactionTestCase
from requests.exceptions import ConnectionError, RequestException, Timeout
from swapper import load_model

from openwisp_utils.tests import catch_signal

from ...vpn_backends import OpenVpn
from .. import settings as app_settings
from ..exceptions import ZeroTierIdentityGenerationError
from ..settings import API_TASK_RETRY_OPTIONS
from ..signals import config_modified, vpn_peers_changed, vpn_server_modified
from ..tasks import create_vpn_dh
from .utils import (
    CreateConfigTemplateMixin,
    TestVpnX509Mixin,
    TestVxlanWireguardVpnMixin,
    TestWireguardVpnMixin,
    TestZeroTierVpnMixin,
)

Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
VpnClient = load_model('config', 'VpnClient')
Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')
Subnet = load_model('openwisp_ipam', 'Subnet')
IpAddress = load_model('openwisp_ipam', 'IpAddress')


class BaseTestVpn(TestVpnX509Mixin, CreateConfigTemplateMixin):
    maxDiff = None


class TestVpn(BaseTestVpn, TestCase):
    """
    tests for Vpn model
    """

    def test_config_not_none(self):
        v = Vpn(
            name='test',
            host='vpn1.test.com',
            ca=self._create_ca(),
            backend=self._BACKENDS['openvpn'],
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
            backend=self._BACKENDS['openvpn'],
        )
        self.assertIs(v.backend_class, OpenVpn)

    def test_backend_instance(self):
        v = Vpn(
            name='test',
            host='vpn1.test.com',
            ca=self._create_ca(),
            backend=self._BACKENDS['openvpn'],
            config={},
        )
        self.assertIsInstance(v.backend_instance, OpenVpn)

    def test_validation(self):
        config = {'openvpn': {'invalid': True}}
        v = Vpn(
            name='test',
            host='vpn1.test.com',
            ca=self._create_ca(),
            backend=self._BACKENDS['openvpn'],
            config=config,
        )
        with self.subTest('test invalid openvpn key'):
            with self.assertRaises(ValidationError):
                v.full_clean()

        with self.subTest('test missing openvpn key'):
            del v.backend_instance
            v.config = {'files': []}
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

    def test_vpn_client_auto_cert_revokes_cert(self):
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
        self.assertEqual(Cert.objects.filter(pk=cert_pk, revoked=True).count(), 1)

    def test_vpn_client_cert_post_deletes_cert(self):
        org = self._get_org()
        vpn = self._create_vpn()
        t = self._create_template(name='vpn-test', type='vpn', vpn=vpn, auto_cert=True)
        c = self._create_config(organization=org)
        c.templates.add(t)
        vpnclient = c.vpnclient_set.first()
        cert_pk = vpnclient.cert.pk
        self.assertEqual(Cert.objects.filter(pk=cert_pk).count(), 1)
        vpnclient.cert.delete()
        self.assertEqual(VpnClient.objects.filter(pk=vpnclient.pk).count(), 0)
        self.assertEqual(Cert.objects.filter(pk=cert_pk).count(), 0)

    def test_vpn_cert_and_ca_mismatch(self):
        ca = self._create_ca()
        different_ca = self._create_ca(common_name='different-ca')
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
            backend=self._BACKENDS['openvpn'],
            config=self._vpn_config,
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
        del context_keys['vpn_host']
        del context_keys['vpn_port']
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
        del context_keys['vpn_host']
        del context_keys['vpn_port']
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

    def test_vpn_client_deletion(self):
        org = self._get_org()
        vpn = self._create_vpn()
        c = self._create_config(organization=org)

        def _assert_vpn_client_cert(cert, vpn_client, cert_ct, vpn_client_ct):
            self.assertEqual(Cert.objects.filter(pk=cert.pk).count(), 1)
            self.assertEqual(VpnClient.objects.filter(pk=vpn_client.pk).count(), 1)
            vpnclient.delete()
            self.assertEqual(
                Cert.objects.filter(pk=cert.pk, revoked=False).count(), cert_ct
            )
            self.assertEqual(
                VpnClient.objects.filter(pk=vpn_client.pk).count(), vpn_client_ct
            )

        with self.subTest(
            'Test VpnClient post_delete handler when "auto_cert" field is set to "True"'
        ):
            t = self._create_template(
                name='vpn-test-1', type='vpn', vpn=vpn, auto_cert=True
            )
            c.templates.add(t)
            vpnclient = c.vpnclient_set.first()
            cert = vpnclient.cert
            _assert_vpn_client_cert(cert, vpnclient, 0, 0)

        with self.subTest(
            'Test VpnClient post_delete handler when "auto_cert" field is set to "False"'  # noqa
        ):
            t = self._create_template(
                name='vpn-test-2', type='vpn', vpn=vpn, auto_cert=True
            )
            c.templates.add(t)
            vpnclient = c.vpnclient_set.first()
            cert = vpnclient.cert
            # Set auto_cert field to false
            vpnclient.auto_cert = False
            vpnclient.full_clean()
            vpnclient.save()
            _assert_vpn_client_cert(cert, vpnclient, 1, 0)

    def test_vpn_client_get_common_name(self):
        vpn = self._create_vpn()
        d = self._create_device()
        c = self._create_config(device=d)
        client = VpnClient(vpn=vpn, config=c, auto_cert=True)
        self.assertIn(
            '{mac_address}-{name}'.format(**d.__dict__),
            client._get_common_name(),
        )
        d.name = d.mac_address
        self.assertIn(d.mac_address, client._get_common_name())

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
            'vpn_host': 'vpn_host_{0}'.format(pk),
            'vpn_port': 'vpn_port_{0}'.format(pk),
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
        client = VpnClient(
            vpn=vpn, config=c, auto_cert=True, template=self._create_template()
        )
        client.full_clean()
        client.save()
        # The last 9 characters gets truncated and replaced with unique id
        self.assertIn(
            '{mac_address}-{name}'.format(**d.__dict__)[:-9], client._get_common_name()
        )
        self.assertEqual(len(client._get_common_name()), 64)
        cert = Cert.objects.filter(organization=org, name=device_name)
        self.assertEqual(cert.count(), 1)
        self.assertEqual(cert.first().common_name[:-9], client._get_common_name()[:-9])

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

    def test_vpn_name_unique_validation(self):
        org = self._get_org()
        vpn1 = self._create_vpn(name='test', organization=org)
        self.assertEqual(vpn1.name, 'test')
        org2 = self._create_org(name='test org2', slug='test-org2')

        with self.subTest('vpn of other org can have the same name'):
            try:
                vpn2 = self._create_vpn(name='test', organization=org2)
            except Exception as e:
                self.fail(f'Unexpected exception: {e}')
            self.assertEqual(vpn2.name, 'test')

        with self.subTest('vpn of shared org cannot have the same name'):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_vpn(name='test', organization=None)
            message_dict = context_manager.exception.message_dict
            self.assertIn('name', message_dict)
            self.assertIn(
                'There is already a vpn of another organization',
                message_dict['name'][0],
            )

        with self.subTest('new vpn of org cannot have the same name as shared vpn'):
            shared = self._create_vpn(name='new', organization=None)
            with self.assertRaises(ValidationError) as context_manager:
                self._create_vpn(name='new', organization=org2)
            message_dict = context_manager.exception.message_dict
            self.assertIn('name', message_dict)
            self.assertIn(
                'There is already another shared vpn', message_dict['name'][0]
            )

        with self.subTest('ensure object itself is excluded'):
            try:
                shared.full_clean()
            except Exception as e:
                self.fail(f'Unexpected exception {e}')

        with self.subTest('cannot have two shared vpns with same name'):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_vpn(name='new', organization=None)
            message_dict = context_manager.exception.message_dict
            self.assertIn('name', message_dict)

    def test_is_backend_type(self):
        vpn = Vpn(backend=self._BACKENDS['openvpn'])
        self.assertTrue(vpn._is_backend_type('openvpn'))
        vpn.backend = self._BACKENDS['wireguard']
        self.assertTrue(vpn._is_backend_type('wireguard'))
        self.assertFalse(vpn._is_backend_type('openvpn'))

    def test_cert_validation(self):
        with self.subTest('test certs required case'):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_vpn(ca=None)
            message_dict = context_manager.exception.message_dict
            self.assertIn('ca', message_dict)
            self.assertIn('CA is required with this VPN backend', message_dict['ca'])


class TestVpnTransaction(BaseTestVpn, TestWireguardVpnMixin, TransactionTestCase):
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

    def test_vpn_server_change_invalidates_device_cache(self):
        device, vpn, template = self._create_wireguard_vpn_template()
        with catch_signal(
            vpn_server_modified
        ) as mocked_vpn_server_modified, catch_signal(
            config_modified
        ) as mocked_config_modified:
            vpn.host = 'localhost'
            vpn.save(update_fields=['host'])
        mocked_vpn_server_modified.assert_called_once_with(
            signal=vpn_server_modified, sender=Vpn, instance=vpn
        )
        mocked_config_modified.assert_called_once_with(
            signal=config_modified,
            sender=Config,
            instance=device.config,
            previous_status='modified',
            action='related_template_changed',
            config=device.config,
            device=device,
        )


class TestWireguard(BaseTestVpn, TestWireguardVpnMixin, TestCase):
    def test_wireguard_config_creation(self):
        vpn = self._create_wireguard_vpn()

        with self.subTest('test key generation'):
            self.assertIsNotNone(vpn.public_key)
            self.assertEqual(len(vpn.public_key), 44)
            self.assertIsNotNone(vpn.private_key)
            self.assertEqual(len(vpn.private_key), 44)

        with self.subTest('test context'):
            context = vpn.get_context()
            self.assertEqual(context['public_key'], vpn.public_key)
            self.assertEqual(context['private_key'], vpn.private_key)
            self.assertEqual(context['subnet'], str(vpn.subnet.subnet))
            self.assertEqual(
                context['subnet_prefixlen'], str(vpn.subnet.subnet.prefixlen)
            )
            self.assertEqual(context['ip_address'], vpn.ip.ip_address)

        with self.subTest('test context keys'):
            context_keys = vpn._get_auto_context_keys()
            self.assertIn('public_key', context_keys)
            self.assertIn('ip_address', context_keys)
            self.assertIn('server_ip_address', context_keys)
            self.assertIn('server_ip_network', context_keys)

    def test_auto_cert_false(self):
        device, vpn, template = self._create_wireguard_vpn_template(auto_cert=False)
        vpnclient_qs = device.config.vpnclient_set
        self.assertEqual(vpnclient_qs.count(), 1)
        self.assertEqual(IpAddress.objects.count(), 1)
        vpnclient = vpnclient_qs.first()
        self.assertEqual(vpnclient.private_key, '')
        self.assertEqual(vpnclient.public_key, '')

    def test_ip_deleted_when_vpnclient_deleted(self):
        device, vpn, template = self._create_wireguard_vpn_template()
        self.assertEqual(IpAddress.objects.count(), 2)
        vpnclient_qs = device.config.vpnclient_set
        self.assertEqual(vpnclient_qs.count(), 1)
        vpnclient_qs.first().delete()
        self.assertEqual(IpAddress.objects.count(), 1)

    def test_ip_deleted_when_device_deleted(self):
        device, vpn, template = self._create_wireguard_vpn_template()
        self.assertEqual(device.config.vpnclient_set.count(), 1)
        device.delete(check_deactivated=False)
        self.assertEqual(IpAddress.objects.count(), 1)

    def test_delete_vpnclient_ip(self):
        device, vpn, template = self._create_wireguard_vpn_template()
        self.assertEqual(device.config.vpnclient_set.count(), 1)
        vpnclient = device.config.vpnclient_set.first()
        vpnclient.ip.delete()
        self.assertEqual(device.config.vpnclient_set.count(), 1)
        self.assertEqual(IpAddress.objects.count(), 1)

    def test_ip_within_subnet(self):
        org = self._get_org()
        subnet1 = self._create_subnet(subnet='10.0.1.0/24', organization=org)
        subnet2 = self._create_subnet(subnet='10.0.2.0/24', organization=org)
        ip_subnet2 = subnet2.request_ip()
        with self.assertRaises(ValidationError) as context_manager:
            self._create_wireguard_vpn(organization=org, subnet=subnet1, ip=ip_subnet2)
        message_dict = context_manager.exception.message_dict
        self.assertIn('ip', message_dict)
        self.assertIn(
            'VPN IP address must be within the VPN subnet', message_dict['ip']
        )

    def test_wireguard_schema(self):
        with self.subTest('wireguard schema shall be valid'):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_wireguard_vpn(config={'wireguard': []})
            self.assertIn(
                'Invalid configuration triggered by "#/wireguard"',
                str(context_manager.exception),
            )
            # delete subnet created for previous assertion
            Subnet.objects.all().delete()

        with self.subTest('wireguard property shall be present'):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_wireguard_vpn(config={})
            self.assertIn('wireguard', str(context_manager.exception))
            self.assertIn('is a required property', str(context_manager.exception))

    def test_auto_client(self):
        device, vpn, template = self._create_wireguard_vpn_template()
        auto = vpn.auto_client(template_backend_class=template.backend_class)
        context_keys = vpn._get_auto_context_keys()
        for key in context_keys.keys():
            context_keys[key] = '{{%s}}' % context_keys[key]
        expected = template.backend_class.wireguard_auto_client(
            host=context_keys['vpn_host'],
            server=self._vpn_config['wireguard'][0],
            **context_keys,
        )
        self.assertEqual(auto, expected)

    def test_change_vpn_backend(self):
        vpn = self._create_vpn(name='new', backend=self._BACKENDS['openvpn'])
        subnet = self._create_subnet(
            name='wireguard', subnet='10.0.0.0/16', organization=vpn.organization
        )
        ca = vpn.ca

        vpn.backend = self._BACKENDS['wireguard']
        vpn.subnet = subnet
        vpn.full_clean()
        vpn.save()
        self.assertEqual(vpn.ca, None)
        self.assertEqual(vpn.cert, None)
        self.assertEqual(vpn.subnet, subnet)
        self.assertNotEqual(vpn.ip, None)

        vpn.backend = self._BACKENDS['openvpn']
        vpn.ca = ca
        vpn.full_clean()
        vpn.save()
        self.assertEqual(vpn.public_key, '')
        self.assertEqual(vpn.private_key, '')
        self.assertEqual(vpn.subnet, subnet)
        self.assertNotEqual(vpn.ip, None)

    def test_wireguard_vpn_without_subnet(self):
        with self.assertRaises(ValidationError) as context_manager:
            self._create_wireguard_vpn(subnet=None)
        expected_error_dict = {'subnet': ['Subnet is required for this VPN backend.']}
        self.assertEqual(expected_error_dict, context_manager.exception.message_dict)

    def test_change_vpn_backend_with_vpnclient(self):
        vpn = self._create_vpn(name='new', backend=self._BACKENDS['openvpn'])
        subnet = self._create_subnet(
            name='wireguard', subnet='10.0.0.0/16', organization=vpn.organization
        )
        template = self._create_template(name='VPN', type='vpn', vpn=vpn)
        config = self._create_config(organization=self._get_org())
        config.templates.add(template)
        self.assertEqual(VpnClient.objects.count(), 1)

        with self.subTest(
            'Test validation error is not raised when backend is unchanged'
        ):
            try:
                vpn.full_clean()
            except ValidationError as error:
                self.fail(f'Unexpected ValidationError: {error}')

        with self.subTest('Test validation error is raised when backend is changed'):
            with self.assertRaises(ValidationError) as context_manager:
                vpn.backend = self._BACKENDS['wireguard']
                vpn.subnet = subnet
                vpn.full_clean()
            expected_error_dict = {
                'backend': [
                    'Backend cannot be changed because the VPN is currently in use.'
                ]
            }
            self.assertDictEqual(
                context_manager.exception.message_dict, expected_error_dict
            )


class TestWireguardTransaction(BaseTestVpn, TestWireguardVpnMixin, TransactionTestCase):
    def test_auto_peer_configuration(self):
        self.assertEqual(IpAddress.objects.count(), 0)
        device, vpn, template = self._create_wireguard_vpn_template()
        vpnclient_qs = device.config.vpnclient_set
        self.assertEqual(vpnclient_qs.count(), 1)
        self.assertEqual(IpAddress.objects.count(), 2)

        with self.subTest('caching'):
            with self.assertNumQueries(0):
                vpn_config = vpn.get_config()['wireguard'][0]

        self.assertEqual(len(vpn_config.get('peers', [])), 1)
        self.assertEqual(
            vpn_config['peers'][0],
            {
                'public_key': vpnclient_qs.first().public_key,
                'allowed_ips': '10.0.0.2/32',
            },
        )

        with self.subTest('test VPN related device context'):
            context = device.get_context()
            pk = vpn.pk.hex
            self.assertEqual(context[f'vpn_host_{pk}'], vpn.host)
            self.assertEqual(context[f'ip_address_{pk}'], '10.0.0.2')
            self.assertEqual(context[f'server_ip_address_{pk}'], '10.0.0.1')
            self.assertEqual(context[f'server_ip_network_{pk}'], '10.0.0.1/32')
            self.assertEqual(context[f'vpn_subnet_{pk}'], '10.0.0.0/16')
            self.assertEqual(context[f'public_key_{pk}'], vpn.public_key)

        with self.subTest('cache update when a new peer is added'):
            device2 = self._create_device_config(
                device_opts={
                    'name': 'test2',
                    'mac_address': '11:11:22:33:44:55',
                    'organization': device.organization,
                }
            )
            device2.config.templates.add(template)
            # cache is invalidated and updated, hence no queries expected
            with self.assertNumQueries(0):
                vpn_config = vpn.get_config()['wireguard'][0]
            self.assertEqual(len(vpn_config.get('peers', [])), 2)

        with self.subTest('cache updated when a new peer is deleted'):
            device2.delete(check_deactivated=False)
            # cache is invalidated but not updated
            # hence we expect queries to be generated
            with self.assertNumQueries(1):
                vpn_config = vpn.get_config()['wireguard'][0]
            self.assertEqual(len(vpn_config.get('peers', [])), 1)

        with self.subTest('other config options not affected by cache'):
            vpn.config['wireguard'][0]['name'] = 'wg2'
            vpn.config['wireguard'][0]['port'] = 51821
            with self.assertNumQueries(0):
                config = vpn.get_config()
            self.assertEqual(config['wireguard'][0]['name'], 'wg2')
            self.assertEqual(config['wireguard'][0]['port'], 51821)

    def test_update_vpn_server_configuration(self):
        device, vpn, template = self._create_wireguard_vpn_template()
        vpn_client = device.config.vpnclient_set.first()
        vpn.save()
        with self.subTest('Webhook endpoint and authentication endpoint is absent'):
            with mock.patch('logging.Logger.info') as mocked_logger:
                post_save.send(
                    instance=vpn_client, sender=vpn_client._meta.model, created=False
                )
                mocked_logger.assert_called_once_with(
                    f'Cannot update configuration of {vpn.name} VPN server, '
                    'webhook endpoint and authentication token are empty.'
                )

        with self.subTest('Webhook endpoint and authentication endpoint is present'):
            vpn.webhook_endpoint = 'https://example.com'
            vpn.auth_token = 'super-secret-token'
            vpn.save()
            vpn_client.refresh_from_db()

            with mock.patch(
                'openwisp_controller.config.tasks.logger.info'
            ) as mocked_logger, mock.patch(
                'requests.post', return_value=HttpResponse()
            ):
                post_save.send(
                    instance=vpn_client, sender=vpn_client._meta.model, created=False
                )
                mocked_logger.assert_called_once_with(
                    f'Triggered update webhook of VPN Server UUID: {vpn.pk}'
                )

            with mock.patch('logging.Logger.error') as mocked_logger, mock.patch(
                'requests.post', return_value=HttpResponseNotFound()
            ):
                post_save.send(
                    instance=vpn_client, sender=vpn_client._meta.model, created=False
                )
                mocked_logger.assert_called_once_with(
                    'Failed to update VPN Server configuration. '
                    f'Response status code: 404, VPN Server UUID: {vpn.pk}'
                )

    def test_vpn_peers_changed(self):
        with self.subTest('VpnClient created'):
            with catch_signal(vpn_peers_changed) as handler:
                device, vpn, template = self._create_wireguard_vpn_template()
                handler.assert_called_once()

        with self.subTest('VpnClient deleted'):
            with catch_signal(vpn_peers_changed) as handler:
                device.config.templates.remove(template)
                handler.assert_called_once()


class TestVxlan(BaseTestVpn, TestVxlanWireguardVpnMixin, TestCase):
    def test_vxlan_config_creation(self):
        tunnel, subnet = self._create_vxlan_tunnel()
        template = self._create_template(
            name='vxlan-wireguard',
            type='vpn',
            vpn=tunnel,
            organization=tunnel.organization,
            auto_cert=True,
        )
        with self.subTest('vni 1'):
            d1 = self._create_device()
            c1 = self._create_config(device=d1)
            client = VpnClient(vpn=tunnel, config=c1, auto_cert=True, template=template)
            client.full_clean()
            client.save()
            client.refresh_from_db()
            self.assertEqual(client.vni, 1)

        with self.subTest('vni 2'):
            d2 = self._create_device(name='d2', mac_address='16:DB:7F:E8:50:01')
            c2 = self._create_config(device=d2)
            client = VpnClient(vpn=tunnel, config=c2, auto_cert=True, template=template)
            client.full_clean()
            client.save()
            client.refresh_from_db()
            self.assertEqual(client.vni, 2)

        with self.subTest('test context keys'):
            context_keys = tunnel._get_auto_context_keys()
            self.assertIn('vni', context_keys)

        with self.subTest('test VPN related device context'):
            context = d1.get_context()
            pk = tunnel.pk.hex
            self.assertEqual(context[f'vpn_host_{pk}'], tunnel.host)
            self.assertEqual(context[f'ip_address_{pk}'], '10.0.0.2')
            self.assertEqual(context[f'server_ip_address_{pk}'], '10.0.0.1')
            self.assertEqual(context[f'server_ip_network_{pk}'], '10.0.0.1/32')
            self.assertEqual(context[f'vpn_subnet_{pk}'], '10.0.0.0/16')
            self.assertEqual(context[f'vni_{pk}'], '1')

        with self.subTest('auto_cert=False'):
            d3 = self._create_device(name='d3', mac_address='16:DB:7F:E8:50:03')
            c3 = self._create_config(device=d3)
            client = VpnClient(
                vpn=tunnel, config=c3, auto_cert=False, template=template
            )
            client.full_clean()
            client.save()
            client.refresh_from_db()
            self.assertEqual(client.vni, None)

    def test_duplicate_vxlan_tunnels_same_vni(self):
        tunnel, subnet = self._create_vxlan_tunnel()
        template = self._create_template(
            name='vxlan-wireguard',
            type='vpn',
            vpn=tunnel,
            organization=tunnel.organization,
            auto_cert=True,
        )
        d1 = self._create_device()
        c1 = self._create_config(device=d1)
        client = VpnClient(vpn=tunnel, config=c1, vni=1, template=template)
        client.full_clean()
        client.save()
        with self.subTest('Test server configuration does not define VNI'):
            d2 = self._create_device(name='d2', mac_address='16:DB:7F:E8:50:01')
            c2 = self._create_config(device=d2)
            client = VpnClient(vpn=tunnel, config=c2, vni=1, template=template)
            with self.assertRaises(ValidationError) as context_manager:
                client.full_clean()
            message_dict = context_manager.exception.message_dict
            self.assertIn('__all__', message_dict)
            self.assertEqual(
                message_dict['__all__'],
                ['VPN client with this Vpn and Vni already exists.'],
            )

        with self.subTest('Test server configuration defines VNI'):
            tunnel.config['vxlan'] = [{'interface': 'vxlan1', 'vni': 1}]
            tunnel.full_clean()
            tunnel.save()
            client = VpnClient(vpn=tunnel, config=c2, vni=1, template=template)
            client.full_clean()
            client.save()

    def test_vxlan_schema(self):
        with self.assertRaises(ValidationError) as context_manager:
            self._create_vxlan_tunnel(config={'wireguard': []})
            self.assertIn(
                'Invalid configuration triggered by "#/wireguard"',
                str(context_manager.exception),
            )
        with self.assertRaises(ValidationError) as context_manager:
            self._create_vxlan_tunnel(config={})
            self.assertIn(
                'Invalid configuration triggered by "#/wireguard"',
                str(context_manager.exception),
            )

    def test_auto_client(self):
        device, vpn, template = self._create_vxlan_vpn_template()
        auto = vpn.auto_client(template_backend_class=template.backend_class)
        context_keys = vpn._get_auto_context_keys()
        for key in context_keys.keys():
            context_keys[key] = '{{%s}}' % context_keys[key]
        expected = template.backend_class.vxlan_wireguard_auto_client(
            host=context_keys['vpn_host'],
            server=self._vpn_config['wireguard'][0],
            **context_keys,
        )
        self.assertEqual(auto, expected)


class TestVxlanTransaction(
    BaseTestVpn, TestVxlanWireguardVpnMixin, TransactionTestCase
):
    def test_auto_peer_configuration(self):
        self.assertEqual(IpAddress.objects.count(), 0)
        device, vpn, template = self._create_vxlan_vpn_template()
        vpnclient_qs = device.config.vpnclient_set
        self.assertEqual(vpnclient_qs.count(), 1)
        self.assertEqual(IpAddress.objects.count(), 2)

        with self.subTest('caching'):
            with self.assertNumQueries(0):
                config = vpn.get_config()

        self.assertEqual(len(config['files']), 1)
        peers = json.loads(config['files'][0]['contents'])
        self.assertIsInstance(peers, list)
        self.assertEqual(len(peers), 1)
        self.assertEqual(
            peers[0],
            {'vni': vpnclient_qs.first().vni, 'remote': '10.0.0.2'},
        )

        with self.subTest('cache update when a new peer is added'):
            device2 = self._create_device_config(
                device_opts={
                    'name': 'test2',
                    'mac_address': '11:11:22:33:44:55',
                    'organization': device.organization,
                }
            )
            device2.config.templates.add(template)
            # cache is invalidated and updated, hence no queries expected
            with self.assertNumQueries(0):
                config = vpn.get_config()
            peers = json.loads(config['files'][0]['contents'])
            self.assertEqual(len(peers), 2)

        with self.subTest('cache updated when a new peer is deleted'):
            device2.delete(check_deactivated=False)
            # cache is invalidated but not updated
            # hence we expect queries to be generated
            with self.assertNumQueries(2):
                config = vpn.get_config()
            peers = json.loads(config['files'][0]['contents'])
            self.assertEqual(len(peers), 1)

        with self.subTest('other config options not affected by cache'):
            vpn.config['wireguard'][0]['name'] = 'wg2'
            vpn.config['wireguard'][0]['port'] = 51821
            with self.assertNumQueries(0):
                config = vpn.get_config()
            self.assertEqual(config['wireguard'][0]['name'], 'wg2')
            self.assertEqual(config['wireguard'][0]['port'], 51821)

    def test_unicast_vxlan_tunnels(self):
        tunnel, _ = self._create_vxlan_tunnel(
            config={
                'wireguard': [{'name': 'wg0', 'port': 51820}],
                'vxlan': [{'name': 'vxlan1', 'vni': 1}],
            }
        )
        device1 = self._create_device_config(
            device_opts={'organization': tunnel.organization}
        )
        device2 = self._create_device_config(
            device_opts={
                'organization': tunnel.organization,
                'name': 'device2',
                'mac_address': '16:DB:7F:E8:50:01',
            }
        )
        vpn_template = self._create_template(
            name='vxlan-wireguard',
            type='vpn',
            vpn=tunnel,
            organization=tunnel.organization,
            auto_cert=True,
        )
        device1.config.templates.add(vpn_template)
        device2.config.templates.add(vpn_template)
        self.assertEqual(VpnClient.objects.count(), 2)
        self.assertListEqual(
            tunnel._get_vxlan_peers(),
            [
                {'interface': 'vxlan1', 'remote': '10.0.0.2', 'vni': 1},
                {'interface': 'vxlan1', 'remote': '10.0.0.3', 'vni': 1},
            ],
        )


class TestZeroTier(BaseTestVpn, TestZeroTierVpnMixin, TestCase):
    _ZT_SERVICE_REQUESTS = 'openwisp_controller.config.api.zerotier_service.requests'
    _ZT_GENERATE_IDENTITY_SUBPROCESS = 'openwisp_controller.config.base.vpn.subprocess'

    def _set_subprocess_mock(self, mock_sub):
        mock_stdout = mock.MagicMock()
        mock_stdout.stdout.decode.return_value = self._TEST_ZT_MEMBER_CONFIG['identity']
        mock_sub.run.return_value = mock_stdout

    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_config_creation(self, mock_requests):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200)
        ]
        vpn = self._create_zerotier_vpn()

        with self.subTest('test context'):
            context = vpn.get_context()
            self.assertEqual(context['subnet'], str(vpn.subnet.subnet))
            self.assertEqual(
                context['subnet_prefixlen'], str(vpn.subnet.subnet.prefixlen)
            )
            self.assertEqual(context['ip_address'], vpn.ip.ip_address)
            # Make sure zerotier network related context keys are present
            self.assertEqual(context['node_id'], vpn.node_id)
            self.assertEqual(context['network_id'], vpn.network_id)

        with self.subTest('test context keys'):
            context_keys = vpn._get_auto_context_keys()
            self.assertIn('vpn_host', context_keys)
            self.assertIn('vpn_port', context_keys)
            self.assertIn('ip_address', context_keys)
            self.assertIn('server_ip_address', context_keys)
            self.assertIn('server_ip_network', context_keys)
            # Make sure zerotier network related context keys are present
            self.assertIn('node_id', context_keys)
            self.assertIn('network_id', context_keys)
            self.assertIn('network_name', context_keys)

    @mock.patch(_ZT_GENERATE_IDENTITY_SUBPROCESS)
    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_auto_cert_false(self, mock_requests, mock_subprocess):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200)
        ]
        self._set_subprocess_mock(mock_subprocess)
        device, vpn, template = self._create_zerotier_vpn_template(auto_cert=False)
        vpnclient_qs = device.config.vpnclient_set
        self.assertEqual(vpnclient_qs.count(), 1)
        self.assertEqual(IpAddress.objects.count(), 1)
        # When auto_cert is 'False', make sure subprocess.run is not called
        self.assertEqual(mock_subprocess.run.call_count, 0)
        vpnclient = vpnclient_qs.first()
        self.assertEqual(vpnclient.zerotier_member_id, '')
        self.assertEqual(vpnclient.secret, '')
        self.assertEqual(vpnclient.private_key, '')
        self.assertEqual(vpnclient.public_key, '')

    @mock.patch(_ZT_GENERATE_IDENTITY_SUBPROCESS)
    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_ip_deleted_when_vpnclient_deleted(self, mock_requests, mock_subprocess):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200)
        ]
        self._set_subprocess_mock(mock_subprocess)
        device, vpn, template = self._create_zerotier_vpn_template()
        self.assertEqual(IpAddress.objects.count(), 2)
        self.assertEqual(mock_subprocess.run.call_count, 1)
        vpnclient_qs = device.config.vpnclient_set
        self.assertEqual(vpnclient_qs.count(), 1)
        vpnclient_qs.first().delete()
        self.assertEqual(IpAddress.objects.count(), 1)

    @mock.patch(_ZT_GENERATE_IDENTITY_SUBPROCESS)
    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_ip_deleted_when_device_deleted(self, mock_requests, mock_subprocess):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200)
        ]
        self._set_subprocess_mock(mock_subprocess)
        device, vpn, template = self._create_zerotier_vpn_template()
        self.assertEqual(mock_subprocess.run.call_count, 1)
        self.assertEqual(device.config.vpnclient_set.count(), 1)
        self.assertEqual(IpAddress.objects.count(), 2)
        device.delete(check_deactivated=False)
        self.assertEqual(IpAddress.objects.count(), 1)

    @mock.patch(_ZT_GENERATE_IDENTITY_SUBPROCESS)
    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_delete_vpnclient_ip(self, mock_requests, mock_subprocess):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200)
        ]
        self._set_subprocess_mock(mock_subprocess)
        device, vpn, template = self._create_zerotier_vpn_template()
        self.assertEqual(mock_subprocess.run.call_count, 1)
        self.assertEqual(device.config.vpnclient_set.count(), 1)
        self.assertEqual(IpAddress.objects.count(), 2)
        vpnclient = device.config.vpnclient_set.first()
        vpnclient.ip.delete()
        self.assertEqual(device.config.vpnclient_set.count(), 1)
        self.assertEqual(IpAddress.objects.count(), 1)

    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_ip_within_subnet(self, mock_requests):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200)
        ]
        org = self._get_org()
        subnet1 = self._create_subnet(subnet='10.0.1.0/24', organization=org)
        subnet2 = self._create_subnet(subnet='10.150.0.0/24', organization=org)
        ip_subnet2 = subnet2.request_ip()
        with self.assertRaises(ValidationError) as context_manager:
            self._create_zerotier_vpn(organization=org, subnet=subnet1, ip=ip_subnet2)
        message_dict = context_manager.exception.message_dict
        self.assertIn('ip', message_dict)
        self.assertIn(
            'VPN IP address must be within the VPN subnet', message_dict['ip']
        )

    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_creation_error(self, mock_requests):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            # (internal server error)
            self._get_mock_response(500, response={}, exc=RequestException)
        ]
        expected_error = 'Failed to create ZeroTier network, Error: '
        with self.assertRaises(ValidationError) as context_manager:
            self._create_zerotier_vpn()
        # Make sure zt vpn server is not created
        self.assertEqual(Vpn.objects.count(), 0)
        self.assertIn(expected_error, str(context_manager.exception))

    def test_zerotier_schema(self):
        with self.subTest('zerotier schema shall be valid'):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_zerotier_vpn(config={'zerotier': []})
            self.assertIn(
                'Invalid configuration triggered by "#/zerotier"',
                str(context_manager.exception),
            )
        # Delete subnet created for previous assertion
        Subnet.objects.all().delete()

        with self.subTest('zerotier property shall be present'):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_zerotier_vpn(config={})
            self.assertIn('zerotier', str(context_manager.exception))
            self.assertIn('is a required property', str(context_manager.exception))

    @mock.patch(_ZT_GENERATE_IDENTITY_SUBPROCESS)
    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_auto_client(self, mock_requests, mock_subprocess):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200)
        ]
        self._set_subprocess_mock(mock_subprocess)
        device, vpn, template = self._create_zerotier_vpn_template()
        self.assertEqual(mock_subprocess.run.call_count, 1)
        auto = vpn.auto_client(template_backend_class=template.backend_class)
        context_keys = vpn._get_auto_context_keys()
        for key in context_keys.keys():
            context_keys[key] = '{{%s}}' % context_keys[key]
        expected = template.backend_class.zerotier_auto_client(
            name='global',
            networks=[{'id': vpn.network_id, 'ifname': f'owzt{vpn.network_id[-6:]}'}],
            identity_secret=context_keys['secret'],
        )
        self.assertEqual(auto, expected)

    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_change_vpn_backend(self, mock_requests):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200)
        ]
        vpn = self._create_vpn(name='new', backend=self._BACKENDS['openvpn'])
        subnet = self._create_subnet(
            name='test-zerotier-subnet',
            subnet='10.0.0.0/16',
            organization=vpn.organization,
        )
        ca = vpn.ca

        vpn.backend = self._BACKENDS['zerotier']
        vpn.subnet = subnet
        vpn.config = {
            'zerotier': [
                {
                    'private': True,
                    'enableBroadcast': True,
                    'mtu': 2800,
                    'multicastLimit': 32,
                }
            ]
        }
        vpn.auth_token = 'test_auth_token'
        vpn.full_clean()
        vpn.save()
        self.assertEqual(vpn.ca, None)
        self.assertEqual(vpn.cert, None)
        self.assertEqual(vpn.subnet, subnet)
        self.assertNotEqual(vpn.ip, None)

        vpn.backend = self._BACKENDS['openvpn']
        vpn.ca = ca
        vpn.full_clean()
        vpn.save()
        self.assertEqual(vpn.public_key, '')
        self.assertEqual(vpn.private_key, '')
        self.assertEqual(vpn.subnet, subnet)
        self.assertNotEqual(vpn.ip, None)

    def test_zerotier_vpn_without_subnet(self):
        with self.assertRaises(ValidationError) as context_manager:
            self._create_zerotier_vpn(subnet=None)
        expected_error_dict = {'subnet': ['Subnet is required for this VPN backend.']}
        self.assertEqual(expected_error_dict, context_manager.exception.message_dict)

    def test_zerotier_vpn_without_auth_token(self):
        with self.assertRaises(ValidationError) as context_manager:
            self._create_zerotier_vpn(auth_token=None)
        expected_error_dict = {
            'auth_token': ['Auth token is required for this VPN backend']
        }
        self.assertEqual(expected_error_dict, context_manager.exception.message_dict)

    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_vpn_host_validation(self, mock_requests):
        with self.subTest('Test host connection error'):
            # node status (connection error)
            mock_requests.get.side_effect = ConnectionError()
            with self.assertRaises(ValidationError) as context_manager:
                self._create_zerotier_vpn()
            expected_error_dict = {
                'host': ['Failed to connect to the ZeroTier controller, Error: ']
            }
            self.assertEqual(
                expected_error_dict, context_manager.exception.message_dict
            )
        mock_requests.reset_mock()
        # Delete subnet created for previous assertion
        Subnet.objects.all().delete()

        with self.subTest('Test host timeout error'):
            # node status (timeout error)
            mock_requests.get.side_effect = Timeout()
            with self.assertRaises(ValidationError) as context_manager:
                self._create_zerotier_vpn()
            expected_error_dict = {
                'host': ['Failed to connect to the ZeroTier controller, Error: ']
            }
            self.assertEqual(
                expected_error_dict, context_manager.exception.message_dict
            )
        mock_requests.reset_mock()
        Subnet.objects.all().delete()

        with self.subTest('Test auth token unauthorized error'):
            mock_requests.get.side_effect = [self._get_mock_response(401, response={})]
            with self.assertRaises(ValidationError) as context_manager:
                self._create_zerotier_vpn()
            expected_error_dict = {
                'auth_token': [
                    (
                        'Authorization failed for ZeroTier controller, '
                        'ensure you are using the correct authorization token'
                    )
                ]
            }
            self.assertEqual(
                expected_error_dict, context_manager.exception.message_dict
            )
        mock_requests.reset_mock()
        Subnet.objects.all().delete()

        with self.subTest('Test for any other request errors'):
            # node status (internal server error)
            mock_requests.get.side_effect = [
                self._get_mock_response(500, response={}, err='Internal Server Error')
            ]
            with self.assertRaises(ValidationError) as context_manager:
                self._create_zerotier_vpn()
            expected_error_dict = {
                'host': [
                    (
                        'Failed to connect to the ZeroTier controller, '
                        'ensure you are using the correct hostname '
                        '(error: Internal Server Error, status code: 500)'
                    )
                ]
            }
            self.assertEqual(
                expected_error_dict, context_manager.exception.message_dict
            )

    def test_zerotier_change_vpn_backend_with_vpnclient(self):
        vpn = self._create_vpn(name='new', backend=self._BACKENDS['openvpn'])
        subnet = self._create_subnet(
            name='zerotier', subnet='10.0.0.0/16', organization=vpn.organization
        )
        template = self._create_template(name='VPN', type='vpn', vpn=vpn)
        config = self._create_config(organization=self._get_org())
        config.templates.add(template)
        self.assertEqual(VpnClient.objects.count(), 1)

        with self.subTest(
            'Test validation error is not raised when backend is unchanged'
        ):
            try:
                vpn.full_clean()
            except ValidationError as error:
                self.fail(f'Unexpected ValidationError: {error}')

        with self.subTest('Test validation error is raised when backend is changed'):
            with self.assertRaises(ValidationError) as context_manager:
                vpn.backend = self._BACKENDS['zerotier']
                vpn.subnet = subnet
                vpn.full_clean()
            expected_error_dict = {
                'backend': [
                    'Backend cannot be changed because the VPN is currently in use.'
                ]
            }
            self.assertDictEqual(
                context_manager.exception.message_dict, expected_error_dict
            )


class TestZeroTierTransaction(
    BaseTestVpn, TestZeroTierVpnMixin, TestWireguardVpnMixin, TransactionTestCase
):
    _ZT_SERVICE_REQUESTS = 'openwisp_controller.config.api.zerotier_service.requests'
    _ZT_API_TASKS_INFO_LOGGER = 'openwisp_controller.config.tasks_zerotier.logger.info'
    _ZT_API_TASKS_WARN_LOGGER = 'openwisp_controller.config.tasks_zerotier.logger.warn'
    _ZT_API_TASKS_ERR_LOGGER = 'openwisp_controller.config.tasks_zerotier.logger.error'
    # As the locmem cache does not support the redis backend cache.keys() method
    _ZT_API_TASKS_LOCMEM_CACHE_KEYS = f"{settings.CACHES['default']['BACKEND']}.keys"
    _ZT_GENERATE_IDENTITY_SUBPROCESS = 'openwisp_controller.config.base.vpn.subprocess'

    @mock.patch(_ZT_GENERATE_IDENTITY_SUBPROCESS)
    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_auto_clients_configuration(self, mock_requests, mock_subprocess):
        # We are testing zerotier transactions
        # using `mock_requests` calls, this includes
        # background tasks that execute on commit
        # such as `join_network`,`update_network`, `delete_network`, etc

        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200),
            # For controller network join
            self._get_mock_response(200),
            # For controller auth and ip assignment
            self._get_mock_response(200),
            # For member auth and ip assignment
            self._get_mock_response(200),
        ]
        mock_stdout = mock.MagicMock()
        mock_stdout.stdout.decode.return_value = self._TEST_ZT_MEMBER_CONFIG['identity']
        mock_subprocess.run.return_value = mock_stdout
        self.assertEqual(IpAddress.objects.count(), 0)
        device, vpn, template = self._create_zerotier_vpn_template()
        vpnclient_qs = device.config.vpnclient_set
        self.assertEqual(vpnclient_qs.count(), 1)
        self.assertEqual(IpAddress.objects.count(), 2)
        self.assertEqual(mock_subprocess.run.call_count, 1)
        context = device.get_context()

        with self.subTest('Test zerotier vpn related device context'):
            pk = vpn.pk.hex
            self.assertEqual(context[f'vpn_host_{pk}'], vpn.host)
            self.assertEqual(context[f'ip_address_{pk}'], '10.0.0.2')
            self.assertEqual(context[f'server_ip_address_{pk}'], '10.0.0.1')
            self.assertEqual(context[f'server_ip_network_{pk}'], '10.0.0.1/32')
            self.assertEqual(context[f'vpn_subnet_{pk}'], '10.0.0.0/16')
            self.assertEqual(
                context[f'node_id_{pk}'], self._TEST_ZT_NODE_CONFIG['address']
            )
            self.assertEqual(
                context[f'network_id_{pk}'], self._TEST_ZT_NETWORK_CONFIG['id']
            )
            self.assertEqual(
                context[f'network_name_{pk}'], self._TEST_ZT_NETWORK_CONFIG['name']
            )

        with self.subTest('Test zerotier vpn client device context'):
            self.assertEqual(
                context['zerotier_member_id'], self._TEST_ZT_MEMBER_CONFIG['address']
            )
            self.assertEqual(context['secret'], self._TEST_ZT_MEMBER_CONFIG['identity'])

    @mock.patch(_ZT_GENERATE_IDENTITY_SUBPROCESS)
    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_vpn_client_identity_error(self, mock_requests, mock_subprocess):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200),
            # For controller network join
            self._get_mock_response(200),
            # For controller auth and ip assignment
            self._get_mock_response(200),
            # For member auth and ip assignment
            self._get_mock_response(200),
        ]
        self.assertEqual(IpAddress.objects.count(), 0)
        zt_cmd = ['zerotier-idtool generate']
        # command not found, timeout error
        mock_subprocess.run.side_effect = [
            CalledProcessError(returncode=127, cmd=zt_cmd),
            TimeoutExpired(timeout=5, cmd=zt_cmd),
        ]
        mock_subprocess.stderr.return_value = None

        vpn = self._create_zerotier_vpn()
        self.assertEqual(IpAddress.objects.count(), 1)
        template = self._create_template(
            name='test-zerotier-template',
            type='vpn',
            vpn=vpn,
            organization=vpn.organization,
            auto_cert=True,
        )
        device = self._create_device_config()

        with self.subTest(
            'Test zt identity error due to CalledProcessError (zt is not installed)'
        ):
            expected_err = (
                'Unable to generate zerotier identity secret, '
                f"Error: Command '{zt_cmd}' returned non-zero exit status 127."
            )
            with self.assertRaises(ZeroTierIdentityGenerationError) as exc:
                device.config.templates.add(template)

            self.assertEqual(expected_err, str(exc.exception))

        # Delete subnet created for previous assertion
        Subnet.objects.all().delete()

        with self.subTest('Test zt identity error due to TimeoutExpired'):
            expected_err = (
                'Unable to generate zerotier identity secret, '
                f"Error: Command '{zt_cmd}' timed out after 5 seconds"
            )

            with self.assertRaises(ZeroTierIdentityGenerationError) as exc:
                device.config.templates.add(template)
            self.assertEqual(expected_err, str(exc.exception))

    @mock.patch(_ZT_GENERATE_IDENTITY_SUBPROCESS)
    @mock.patch(_ZT_API_TASKS_ERR_LOGGER)
    @mock.patch(_ZT_API_TASKS_WARN_LOGGER)
    @mock.patch(_ZT_API_TASKS_INFO_LOGGER)
    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_vpn_client_template(
        self, mock_requests, mock_info, mock_warn, mock_error, mock_subprocess
    ):
        def _reset_mocks():
            mock_info.reset_mock()
            mock_requests.reset_mock()
            mock_subprocess.reset_mock()

        mock_requests.get.side_effect = [
            # For node status (vpn1)
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG),
            # For node status (vpn2)
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG),
        ]
        mock_requests.post.side_effect = [
            # For create network (vpn1)
            self._get_mock_response(200),
            # For controller network join (vpn1)
            self._get_mock_response(200),
            # For controller auth and ip assignment (vpn1)
            self._get_mock_response(200),
            # For create network (vpn2)
            self._get_mock_response(200),
            # For controller network join (vpn2)
            self._get_mock_response(200),
            # For controller auth and ip assignment (vpn2)
            self._get_mock_response(200),
            # For member auth and ip assignment (wirguard + vpn1)
            self._get_mock_response(200),
            # For member auth and ip assignment (only vpn1)
            self._get_mock_response(200),
            # For member auth and ip assignment (vpn1 + vpn2)
            self._get_mock_response(200),
        ]
        mock_requests.delete.side_effect = [
            # For remove network member (vpn1)
            self._get_mock_response(200),
        ]
        mock_stdout = mock.MagicMock()
        mock_stdout.stdout.decode.return_value = self._TEST_ZT_MEMBER_CONFIG['identity']
        mock_subprocess.run.return_value = mock_stdout
        self.assertEqual(IpAddress.objects.count(), 0)

        subnet1 = self._create_subnet(
            name='test-zerotier-subnet-1', subnet='10.150.0.0/24', organization=None
        )
        subnet2 = self._create_subnet(
            name='test-zerotier-subnet-2', subnet='10.250.0.0/24', organization=None
        )
        zt_vpn1 = self._create_zerotier_vpn(subnet=subnet1)
        zt_vpn2 = self._create_zerotier_vpn(name='test-zerotier-vpn-2', subnet=subnet2)
        device = self._create_device_config()
        vpnclient_qs = device.config.vpnclient_set
        zt1 = self._create_template(
            name='test-zt-template-1',
            type='vpn',
            vpn=zt_vpn1,
            organization=zt_vpn1.organization,
            auto_cert=True,
        )
        zt2 = self._create_template(
            name='test-zt-template-2',
            type='vpn',
            vpn=zt_vpn2,
            organization=zt_vpn2.organization,
            auto_cert=True,
        )
        wg_vpn = self._create_wireguard_vpn()
        wg_template = self._create_template(
            name='wireguard',
            type='vpn',
            vpn=wg_vpn,
            organization=wg_vpn.organization,
            auto_cert=True,
        )
        # Let's add wireguard vpn client template to the device
        device.config.templates.add(wg_template)
        # Ensure ip address objects are created
        # for all three vpn servers and wg vpn client
        self.assertEqual(IpAddress.objects.count(), 4)
        self.assertEqual(vpnclient_qs.count(), 1)
        self.assertEqual(mock_info.call_count, 4)
        self.assertEqual(mock_warn.call_count, 0)
        self.assertEqual(mock_error.call_count, 0)
        self.assertEqual(mock_subprocess.run.call_count, 0)
        self.assertEqual(mock_requests.get.call_count, 2)
        self.assertEqual(mock_requests.post.call_count, 6)
        self.assertEqual(mock_requests.delete.call_count, 0)
        _reset_mocks()

        with self.subTest(
            (
                'Test zt identity generation when different vpn client '
                '(wireguard) template is already applied to the device'
            )
        ):
            device.config.templates.add(zt1)
            # New vpn client object is created
            self.assertEqual(vpnclient_qs.count(), 2)
            self.assertEqual(vpnclient_qs.filter(vpn=zt_vpn1).exists(), True)
            # New ip address object for zt vpn client object is created
            self.assertEqual(IpAddress.objects.count(), 5)
            # Make sure subprocess is called for identity generation
            self.assertEqual(mock_subprocess.run.call_count, 1)
            self.assertEqual(mock_info.call_count, 1)
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_error.call_count, 0)
            self.assertEqual(mock_requests.post.call_count, 1)

        # Now remove zt and wg vpn template from the device
        device.config.templates.remove(zt1)
        device.config.templates.remove(wg_template)
        self.assertEqual(IpAddress.objects.count(), 3)
        self.assertEqual(mock_requests.delete.call_count, 1)
        _reset_mocks()

        with self.subTest(
            (
                'Test zt identity generation when only zt '
                'vpn client template is applied to the device'
            )
        ):
            device.config.templates.add(zt1)
            self.assertEqual(vpnclient_qs.count(), 1)
            self.assertEqual(vpnclient_qs.first().vpn, zt_vpn1)
            # New ip address object for zt vpn client object is created
            self.assertEqual(IpAddress.objects.count(), 4)
            # Make sure subprocess is called for identity generation
            self.assertEqual(mock_subprocess.run.call_count, 1)
            self.assertEqual(mock_info.call_count, 1)
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_error.call_count, 0)
            self.assertEqual(mock_requests.post.call_count, 1)
        _reset_mocks()

        with self.subTest(
            (
                'Test zt no identity generation when different '
                'zt vpn server vpn client template is applied to the device'
            )
        ):
            device.config.templates.add(zt2)
            # New zt vpn client object is created
            self.assertEqual(vpnclient_qs.count(), 2)
            self.assertEqual(vpnclient_qs.first().vpn, zt_vpn1)
            self.assertEqual(vpnclient_qs.last().vpn, zt_vpn2)
            # Ensure that new ip address object are created
            self.assertEqual(IpAddress.objects.count(), 5)
            # Make sure subprocess is not called for identity generation
            self.assertEqual(mock_subprocess.run.call_count, 0)
            self.assertEqual(mock_info.call_count, 1)
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_error.call_count, 0)
            self.assertEqual(mock_requests.post.call_count, 1)

    @mock.patch(_ZT_API_TASKS_ERR_LOGGER)
    @mock.patch(_ZT_API_TASKS_WARN_LOGGER)
    @mock.patch(_ZT_API_TASKS_INFO_LOGGER)
    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_update_vpn_server_configuration(
        self, mock_requests, mock_info, mock_warn, mock_error
    ):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200),
            # For controller network join
            self._get_mock_response(200),
            # For controller auth and ip assignment
            self._get_mock_response(200),
        ]
        # Now create zerotier network
        vpn = self._create_zerotier_vpn()
        self.assertEqual(Vpn.objects.count(), 1)
        self.assertEqual(vpn.name, self._TEST_ZT_NETWORK_CONFIG['name'])
        mock_info.reset_mock()
        mock_requests.reset_mock()

        with self.subTest('Test zerotier successful configuration update'):
            mock_requests.get.side_effect = [
                # For node status
                self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
            ]
            mock_requests.post.side_effect = [
                # For update network
                self._get_mock_response(200),
                # For controller auth and ip assignment
                self._get_mock_response(200),
            ]
            _EXPECTED_INFO_CALLS = [
                mock.call(
                    (
                        f'Successfully updated the configuration of '
                        f'ZeroTier VPN Server with UUID: {vpn.id}'
                    )
                ),
                mock.call(
                    (
                        f'Successfully updated ZeroTier network member: {vpn.node_id}, '
                        f'ZeroTier network: {vpn.network_id}, '
                        f'ZeroTier VPN server UUID: {vpn.id}'
                    )
                ),
            ]
            config = vpn.get_config()['zerotier'][0]
            config.update({'private': True})
            vpn.full_clean()
            vpn.save()
            self.assertEqual(mock_info.call_count, 2)
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_error.call_count, 0)
            mock_info.assert_has_calls(_EXPECTED_INFO_CALLS)
        mock_info.reset_mock()
        mock_requests.reset_mock()

        with self.subTest('Test zerotier configuration update (unrecoverable errors)'):
            mock_requests.get.side_effect = [
                # For node status
                self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
            ]
            mock_requests.post.side_effect = [
                # For update network
                self._get_mock_response(200),
                # For controller auth and ip assignment (bad request)
                self._get_mock_response(
                    400,
                    response={},
                    exc=RequestException,
                ),
            ]
            _EXPECTED_INFO_CALLS = [
                mock.call(
                    (
                        f'Successfully updated the configuration of '
                        f'ZeroTier VPN Server with UUID: {vpn.id}'
                    )
                ),
            ]
            _EXPECTED_ERROR_CALLS = [
                mock.call(
                    (
                        f'Failed to update ZeroTier network member: {vpn.node_id}, '
                        f'ZeroTier network: {vpn.network_id}, '
                        f'ZeroTier VPN server UUID: {vpn.id}, Error: '
                    )
                ),
            ]
            config = vpn.get_config()['zerotier'][0]
            config.update({'private': True})
            vpn.full_clean()
            vpn.save()
            self.assertEqual(mock_info.call_count, 1)
            self.assertEqual(mock_warn.call_count, 0)
            # For unrecoverable error
            self.assertEqual(mock_error.call_count, 1)
            mock_info.assert_has_calls(_EXPECTED_INFO_CALLS)
            mock_error.assert_has_calls(_EXPECTED_ERROR_CALLS)
        mock_info.reset_mock()
        mock_error.reset_mock()
        mock_requests.reset_mock()

        with self.subTest(
            'Test zerotier configuration update '
            'with retry mechanism (recoverable errors)'
        ), mock.patch('celery.app.task.Task.request') as mock_task_request:
            max_retries = API_TASK_RETRY_OPTIONS.get('max_retries')
            mock_task_request.called_directly = False
            config = vpn.get_config()['zerotier'][0]
            config.update({'private': True})

            with self.subTest(
                'Test update when max retry limit is not reached'
            ), self.assertRaises(Retry):
                mock_requests.get.side_effect = [
                    # For node status
                    self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
                ]
                mock_requests.post.side_effect = [
                    # For update network
                    self._get_mock_response(200),
                    # For controller auth and ip assignment
                    # (internal server error)
                    self._get_mock_response(
                        500,
                        response={},
                        exc=RequestException,
                    ),
                ]
                _EXPECTED_INFO_CALLS = [
                    mock.call(
                        (
                            f'Successfully updated the configuration of '
                            f'ZeroTier VPN Server with UUID: {vpn.id}'
                        )
                    ),
                ]
                _EXPECTED_WARN_CALLS = [
                    mock.call(
                        (
                            f'Try [{max_retries - 1}/{max_retries}] Failed to update '
                            f'ZeroTier network member: {vpn.node_id}, '
                            f'ZeroTier network: {vpn.network_id}, '
                            f'ZeroTier VPN server UUID: {vpn.id}, Error: '
                        )
                    ),
                ]
                # Second last retry attempt (4th)
                mock_task_request.retries = max_retries - 1
                vpn.full_clean()
                vpn.save()
            self.assertEqual(mock_info.call_count, 1)
            # Ensure that it logs with the 'warning' level
            self.assertEqual(mock_warn.call_count, 1)
            self.assertEqual(mock_error.call_count, 0)
            mock_info.assert_has_calls(_EXPECTED_INFO_CALLS)
            mock_warn.assert_has_calls(_EXPECTED_WARN_CALLS)
            mock_info.reset_mock()
            mock_warn.reset_mock()
            mock_requests.reset_mock()

            # During the last attempt, the task will give up
            # retrying and raise a 'RequestException',
            # which will be handled and logged as an error
            with self.subTest(
                'Test update when max retry limit is reached'
            ), self.assertRaises(RequestException):
                mock_requests.get.side_effect = [
                    # For node status
                    self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
                ]
                mock_requests.post.side_effect = [
                    # For update network
                    self._get_mock_response(200),
                    # For controller auth and ip assignment
                    # (internal server error)
                    self._get_mock_response(
                        500,
                        response={},
                        exc=RequestException,
                    ),
                ]
                _EXPECTED_INFO_CALLS = [
                    mock.call(
                        (
                            f'Successfully updated the configuration of '
                            f'ZeroTier VPN Server with UUID: {vpn.id}'
                        )
                    ),
                ]
                _EXPECTED_ERROR_CALLS = [
                    mock.call(
                        (
                            f'Try [{max_retries}/{max_retries}] Failed to update '
                            f'ZeroTier network member: {vpn.node_id}, '
                            f'ZeroTier network: {vpn.network_id}, '
                            f'ZeroTier VPN server UUID: {vpn.id}, Error: '
                        )
                    ),
                ]
                # Last retry attempt (5th)
                mock_task_request.retries = max_retries
                vpn.full_clean()
                vpn.save()
            self.assertEqual(mock_info.call_count, 1)
            self.assertEqual(mock_warn.call_count, 0)
            # Ensure that it logs last attempt with the 'error' level
            self.assertEqual(mock_error.call_count, 1)
            mock_info.assert_has_calls(_EXPECTED_INFO_CALLS)
            mock_error.assert_has_calls(_EXPECTED_ERROR_CALLS)

    @mock.patch(_ZT_API_TASKS_LOCMEM_CACHE_KEYS, create=True)
    @mock.patch(_ZT_API_TASKS_ERR_LOGGER)
    @mock.patch(_ZT_API_TASKS_WARN_LOGGER)
    @mock.patch(_ZT_API_TASKS_INFO_LOGGER)
    @mock.patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_vpn_server_deletion(
        self, mock_requests, mock_info, mock_warn, mock_error, mock_locmem_cache_keys
    ):
        def _setup_requests_mocks():
            mock_requests.get.side_effect = [
                # For node status
                self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
            ]
            mock_requests.post.side_effect = [
                # For create network
                self._get_mock_response(200),
                # For controller network join
                self._get_mock_response(200),
                # For controller auth and ip assignment
                self._get_mock_response(200),
            ]
            mock_locmem_cache_keys.return_value = ['test_zt_api_tasks_notification_key']

        def _reset_requests_mocks():
            mock_requests.reset_mock()
            mock_locmem_cache_keys.reset_mock()
            # Delete subnet created for previous assertion
            Subnet.objects.all().delete()

        with self.subTest(
            'Test db transaction fails on vpn.save(), it should delete the zt network'
        ):
            invalid_response = {'test-key': 'raise integrity error on save'}
            mock_requests.get.side_effect = [
                # For node status
                self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
            ]
            mock_requests.post.side_effect = [
                # For create network
                self._get_mock_response(200, response=invalid_response),
            ]
            mock_requests.delete.side_effect = [
                # For delete network
                self._get_mock_response(200, response={}),
                # For controller leave network
                self._get_mock_response(200, response={}),
            ]
            with self.assertRaises(IntegrityError):
                vpn = self._create_zerotier_vpn()
            self.assertEqual(Vpn.objects.count(), 0)
            _EXPECTED_INFO_MSG = (
                'Successfully deleted the ZeroTier VPN Server with UUID:',
                'Successfully left the ZeroTier Network with ID:',
            )
            self.assertEqual(mock_info.call_count, 2)
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_error.call_count, 0)
            self.assertIn(_EXPECTED_INFO_MSG[0], mock_info.call_args_list[0][0][0])
            self.assertIn(_EXPECTED_INFO_MSG[1], mock_info.call_args_list[1][0][0])

        _reset_requests_mocks()
        _setup_requests_mocks()

        with self.subTest('Test post_delete signal triggers deletion of vpn server'):
            vpn = self._create_zerotier_vpn()
            self.assertEqual(Vpn.objects.count(), 1)
            vpn_id = vpn.id
            network_id = vpn.network_id
            # Reset vpn creation logs
            mock_info.reset_mock()
            mock_requests.delete.side_effect = [
                # For delete network
                self._get_mock_response(200, response={}),
                # For controller leave network
                self._get_mock_response(200, response={}),
            ]
            vpn.delete()
            self.assertEqual(Vpn.objects.count(), 0)
            _EXPECTED_INFO_CALLS = [
                mock.call(
                    (
                        f'Successfully deleted the ZeroTier VPN Server '
                        f'with UUID: {vpn_id}, Network ID: {network_id}'
                    )
                ),
                mock.call(
                    f'Successfully left the ZeroTier Network with ID: {network_id}'
                ),
            ]
            self.assertEqual(mock_info.call_count, 2)
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_error.call_count, 0)
            mock_info.assert_has_calls(_EXPECTED_INFO_CALLS)

        _reset_requests_mocks()
        _setup_requests_mocks()

        with self.subTest('Test for zerotier vpn server deletion encountered an error'):
            vpn = self._create_zerotier_vpn()
            vpn_id = vpn.id
            network_id = vpn.network_id
            self.assertEqual(Vpn.objects.count(), 1)
            # Reset vpn creation logs
            mock_info.reset_mock()
            mock_requests.delete.side_effect = [
                # For delete network
                self._get_mock_response(404, response={}, exc=RequestException),
            ]
            vpn.delete()
            self.assertEqual(Vpn.objects.count(), 0)
            _EXPECTED_ERROR_CALLS = [
                mock.call(
                    (
                        'Failed to delete ZeroTier VPN Server with '
                        f'UUID: {vpn_id}, Network ID: {network_id}, as it '
                        'does not exist on the ZeroTier Controller Networks, Error: '
                    )
                ),
            ]
            self.assertEqual(mock_info.call_count, 0)
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_error.call_count, 1)
            mock_error.assert_has_calls(_EXPECTED_ERROR_CALLS)

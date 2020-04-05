from django.conf import settings
from django.core.exceptions import ValidationError

from openwisp_users.tests.utils import TestOrganizationMixin

from ....vpn_backends import OpenVpn
from . import CreateConfigTemplateMixin, TestVpnX509Mixin


class AbstractTestVpn(
    TestOrganizationMixin, TestVpnX509Mixin, CreateConfigTemplateMixin
):
    """
    tests for Vpn model
    """

    maxDiff = None

    def test_config_not_none(self):
        v = self.vpn_model(
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
        v = self.vpn_model(
            name='test',
            host='vpn1.test.com',
            ca=self._create_ca(),
            backend='openwisp_controller.vpn_backends.OpenVpn',
        )
        self.assertIs(v.backend_class, OpenVpn)

    def test_backend_instance(self):
        v = self.vpn_model(
            name='test',
            host='vpn1.test.com',
            ca=self._create_ca(),
            backend='openwisp_controller.vpn_backends.OpenVpn',
            config={},
        )
        self.assertIsInstance(v.backend_instance, OpenVpn)

    def test_validation(self):
        config = {'openvpn': {'invalid': True}}
        v = self.vpn_model(
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
        client = self.vpn_client_model(vpn=vpn, config=c, auto_cert=True)
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
        self.assertEqual(self.cert_model.objects.filter(pk=cert_pk).count(), 1)
        c.delete()
        self.assertEqual(
            self.vpn_client_model.objects.filter(pk=vpnclient.pk).count(), 0
        )
        self.assertEqual(self.cert_model.objects.filter(pk=cert_pk).count(), 0)

    def test_vpn_cert_and_ca_mismatch(self):
        ca = self._create_ca()
        different_ca = self._create_ca()
        cert = self.cert_model(
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
        vpn = self.vpn_model(
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
            self.fail('Mismatch between ca and cert but ' 'ValidationError not raised')

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
                'mode': '0644',
                'contents': context_keys['ca_contents'],
            },
            {
                'path': context_keys['cert_path'],
                'mode': '0644',
                'contents': context_keys['cert_contents'],
            },
            {
                'path': context_keys['key_path'],
                'mode': '0644',
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
                'mode': '0644',
                'contents': context_keys['ca_contents'],
            }
        ]
        self.assertDictEqual(auto, control)

    def test_vpn_client_get_common_name(self):
        vpn = self._create_vpn()
        d = self._create_device()
        c = self._create_config(device=d)
        client = self.vpn_client_model(vpn=vpn, config=c, auto_cert=True)
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

    def test_get_context(self):
        v = self._create_vpn()
        expected = {
            'ca': v.ca.certificate,
            'cert': v.cert.certificate,
            'key': v.cert.private_key,
            'dh': v.dh,
        }
        expected.update(settings.NETJSONCONFIG_CONTEXT)
        self.assertEqual(v.get_context(), expected)

    def test_dh(self):
        v = self._create_vpn()
        v.dh = None
        v.save()
        self.assertIsNotNone(v.dh)
        self.assertNotEqual(v.dh, '')
        self.assertTrue(v.dh.startswith('-----BEGIN DH PARAMETERS-----'))
        self.assertTrue(v.dh.endswith('-----END DH PARAMETERS-----\n'))

    def test_get_context_empty_vpn(self):
        v = self.vpn_model()
        self.assertEqual(v.get_context(), settings.NETJSONCONFIG_CONTEXT)

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

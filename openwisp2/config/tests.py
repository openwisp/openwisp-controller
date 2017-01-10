from django.core.exceptions import ValidationError
from django.test import TestCase

from openwisp2.pki.tests import TestPkiMixin
from openwisp2.tests import TestOrganizationMixin

from ..pki.models import Ca, Cert
from .models import Vpn


class TestConfig(TestCase, TestOrganizationMixin, TestPkiMixin):
    ca_model = Ca
    cert_model = Cert

    _dh = """-----BEGIN DH PARAMETERS-----
MIGHAoGBAMkiqC2kAkjhysnuBORxJgDMdq3JrvaNh1kZW0IkFiyLRyhtYf92atP4
ycYELVoRZoRZ8zp2Y2L71vHRNx5okiXZ1xRWDfEVp7TFVc+oCTTRwJqyq21/DJpe
Qt01H2yL7CvdEUi/gCUJNS9Jm40248nwKgyrwyoS3SjY49CAcEYLAgEC
-----END DH PARAMETERS-----"""
    _vpn_config = {
        "openvpn": [
            {
                "ca": "ca.pem",
                "cert": "cert.pem",
                "dev": "tap0",
                "dev_type": "tap",
                "dh": "dh.pem",
                "key": "key.pem",
                "mode": "server",
                "name": "example-vpn",
                "proto": "udp",
                "tls_server": True
            }
        ]
    }

    def _create_vpn(self, ca_options={}, **kwargs):
        options = dict(name='test',
                       host='vpn1.test.com',
                       ca=None,
                       organization=None,
                       backend='django_netjsonconfig.vpn_backends.OpenVpn',
                       config=self._vpn_config,
                       dh=self._dh)
        options.update(**kwargs)
        if not options['ca']:
            options['ca'] = self._create_ca(**ca_options)
        vpn = Vpn(**options)
        vpn.full_clean()
        vpn.save()
        return vpn

    def test_vpn_with_org(self):
        org = self._create_org()
        vpn = self._create_vpn(organization=org)
        self.assertEqual(vpn.organization_id, org.pk)

    def test_vpn_without_org(self):
        vpn = self._create_vpn()
        self.assertIsNone(vpn.organization)

    def test_vpn_with_shared_ca(self):
        ca = self._create_ca()  # shared CA
        org = self._create_org()
        vpn = self._create_vpn(organization=org, ca=ca)
        self.assertIsNone(ca.organization)
        self.assertEqual(vpn.ca_id, ca.pk)

    def test_vpn_and_ca_different_organization(self):
        org1 = self._create_org()
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
        org1 = self._create_org()
        # shared CA
        ca = self._create_ca()
        # org1 specific cert
        cert = self._create_cert(ca=ca, organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        try:
            self._create_vpn(ca=ca, cert=cert, organization=org2)
        except ValidationError as e:
            self.assertIn('organization', e.message_dict)
            self.assertIn('related certificate match', e.message_dict['organization'][0])
        else:
            self.fail('ValidationError not raised')

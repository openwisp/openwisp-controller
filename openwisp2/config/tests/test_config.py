from django.core.exceptions import ValidationError
from django.test import TestCase

from django_netjsonconfig.tests import CreateTemplateMixin

from . import TestVpnX509Mixin
from ...pki.models import Ca, Cert
from ...tests import TestOrganizationMixin
from ..models import Config, Template, Vpn


class TestConfig(CreateTemplateMixin, TestVpnX509Mixin,
                 TestOrganizationMixin, TestCase):
    ca_model = Ca
    cert_model = Cert
    vpn_model = Vpn
    template_model = Template
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
        c = Config(**options)
        c.full_clean()
        c.save()
        return c

    def test_config_with_org(self):
        org = self._create_org()
        config = self._create_config(organization=org)
        self.assertEqual(config.organization_id, org.pk)

    def test_config_without_org(self):
        try:
            self._create_config()
        except ValidationError as e:
            self.assertIn('organization', e.message_dict)
            self.assertIn('This field', e.message_dict['organization'][0])
        else:
            self.fail('ValidationError not raised')

    def test_config_with_shared_template(self):
        org = self._create_org()
        config = self._create_config(organization=org)
        # shared template
        template = self._create_template()
        # add shared template
        config.templates.add(template)
        self.assertIsNone(template.organization)
        self.assertEqual(config.templates.first().pk, template.pk)

    def test_config_and_template_different_organization(self):
        org1 = self._create_org()
        template = self._create_template(organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        config = self._create_config(organization=org2)
        try:
            config.templates.add(template)
        except ValidationError as e:
            self.assertIn('templates', e.message_dict)
            self.assertIn('do not match the organization', e.message_dict['templates'][0])
        else:
            self.fail('ValidationError not raised')

from django.core.exceptions import ValidationError
from django.test import TestCase

from openwisp_users.tests.utils import TestOrganizationMixin

from . import CreateConfigTemplateMixin, TestVpnX509Mixin
from ..models import Config, Template


class TestConfig(CreateConfigTemplateMixin, TestVpnX509Mixin,
                 TestOrganizationMixin, TestCase):
    config_model = Config
    template_model = Template

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
            self.assertIn('do not match the organization', e.messages[0])
        else:
            self.fail('ValidationError not raised')

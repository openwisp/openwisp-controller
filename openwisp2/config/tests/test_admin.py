from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.test import TestCase

from . import CreateConfigTemplateMixin
from ...tests import TestOrganizationMixin
from ..models import Config, Template


class TestAdmin(CreateConfigTemplateMixin, TestOrganizationMixin, TestCase):
    """
    tests for Config model
    """
    config_model = Config
    template_model = Template

    def setUp(self):
        user_model = get_user_model()
        user_model.objects.create_superuser(username='admin',
                                            password='tester',
                                            email='admin@admin.com')
        self.client.login(username='admin', password='tester')

    def test_config_and_template_different_organization(self):
        org1 = self._create_org()
        template = self._create_template(organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        config = self._create_config(organization=org2)
        path = reverse('admin:config_config_change', args=[config.pk])
        # ensure it fails with error
        response = self.client.post(path, {'templates': str(template.pk), 'key': self.TEST_KEY})
        self.assertIn('errors field-templates', str(response.content))
        # remove conflicting template and ensure doesn't error
        response = self.client.post(path, {'templates': '', 'key': self.TEST_KEY})
        self.assertNotIn('errors field-templates', str(response.content))

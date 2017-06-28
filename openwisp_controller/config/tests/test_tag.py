from django.test import TestCase
from django_netjsonconfig.tests import CreateTemplateMixin

from openwisp_users.tests.utils import TestOrganizationMixin

from ..models import Template


class TestTag(TestOrganizationMixin, CreateTemplateMixin, TestCase):
    """
    tests for Tag model
    """
    template_model = Template

    def test_tag(self):
        t = self._create_template(organization=self._create_org())
        t.tags.add('mesh')
        self.assertEqual(t.tags.filter(name='mesh').count(), 1)

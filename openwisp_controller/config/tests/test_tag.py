from django.test import TestCase
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from .utils import CreateTemplateMixin

Template = load_model('config', 'Template')


class TestTag(TestOrganizationMixin, CreateTemplateMixin, TestCase):
    """
    tests for Tag model
    """

    def test_tag(self):
        t = self._create_template(organization=self._get_org())
        t.tags.add('mesh')
        self.assertEqual(t.tags.filter(name='mesh').count(), 1)

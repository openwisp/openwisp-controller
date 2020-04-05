from openwisp_users.tests.utils import TestOrganizationMixin

from . import CreateTemplateMixin


class AbstractTestTag(TestOrganizationMixin, CreateTemplateMixin):
    """
    tests for Tag model
    """

    def test_tag(self):
        t = self._create_template(organization=self._get_org())
        t.tags.add('mesh')
        self.assertEqual(t.tags.filter(name='mesh').count(), 1)

import unittest

from openwisp2.staticfiles import DependencyFinder
from openwisp2.users.models import Organization


class TestOrganizationMixin(object):
    def _create_org(self, **kwargs):
        options = {
            'name': 'test org',
            'is_active': True,
            'slug': 'test-org'
        }
        options.update(kwargs)
        org = Organization.objects.create(**options)
        return org


class TestStaticFinders(unittest.TestCase):
    def test_dependency_finder(self):
        finder = DependencyFinder()
        self.assertIsInstance(finder.locations, list)

import unittest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import Q

from openwisp2.staticfiles import DependencyFinder
from openwisp2.users.models import Organization, OrganizationUser

user_model = get_user_model()


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


class TestAdminMixin(object):
    def setUp(self):
        user_model.objects.create_superuser(username='admin',
                                            password='tester',
                                            email='admin@admin.com')

    def _login(self, username='admin', password='tester'):
        self.client.login(username=username, password=password)

    def _logout(self):
        self.client.logout()

    operator_permission_filters = []

    def get_operator_permissions(self):
        filters = Q()
        for filter in self.operator_permission_filters:
            filters = filters | Q(**filter)
        return Permission.objects.filter(filters)

    def _create_operator(self, organizations=[]):
        operator = user_model.objects.create_user(username='operator',
                                                  password='tester',
                                                  email='operator@test.com',
                                                  is_staff=True)
        operator.user_permissions.add(*self.get_operator_permissions())
        for organization in organizations:
            OrganizationUser.objects.create(user=operator, organization=organization)
        return operator

    def _test_multitenant_admin(self, url, visible, hidden, select_widget=False):
        """
        reusable test function that ensures different users
        can see the right objects.
        an operator with limited permissions will not be able
        to see the elements contained in ``hidden``, while
        a superuser can see everything.
        """
        self._login(username='operator', password='tester')
        response = self.client.get(url)

        # utility format function
        def _f(el, select_widget=False):
            if select_widget:
                return '{0}</option>'.format(el)
            return el

        # ensure elements in visible list are visible to operator
        for el in visible:
            self.assertContains(response, _f(el, select_widget),
                                msg_prefix='[operator contains]')
        # ensure elements in hidden list are not visible to operator
        for el in hidden:
            self.assertNotContains(response, _f(el, select_widget),
                                   msg_prefix='[operator not-contains]')

        # now become superuser
        self._logout()
        self._login(username='admin', password='tester')
        response = self.client.get(url)
        # ensure all elements are visible to superuser
        all_elements = visible + hidden
        for el in all_elements:
            self.assertContains(response, _f(el, select_widget),
                                msg_prefix='[superuser contains]')


class TestStaticFinders(unittest.TestCase):
    def test_dependency_finder(self):
        finder = DependencyFinder()
        self.assertIsInstance(finder.locations, list)

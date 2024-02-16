from unittest.mock import patch

from django.test import TestCase

from openwisp_users.tests.utils import TestOrganizationMixin

from .. import tasks


class TestHandlers(TestOrganizationMixin, TestCase):
    @patch.object(tasks.invalidate_device_checksum_view_cache, 'delay')
    def test_organization_disabled_handler(self, mocked_task):
        with self.subTest('Test task not executed on creating active orgs'):
            org = self._create_org()
            mocked_task.assert_not_called()

        with self.subTest('Test task executed on changing active to inactive org'):
            org.is_active = False
            org.save()
            mocked_task.assert_called_once()

        mocked_task.reset_mock()
        with self.subTest('Test task not executed on saving inactive org'):
            org.name = 'Changed named'
            org.save()
            mocked_task.assert_not_called()

        with self.subTest('Test task not executed on creating inactive org'):
            inactive_org = self._create_org(
                is_active=False, name='inactive', slug='inactive'
            )
            mocked_task.assert_not_called()

        with self.subTest('Test task not executed on changing inactive to active org'):
            inactive_org.is_active = True
            inactive_org.save()
            mocked_task.assert_not_called()

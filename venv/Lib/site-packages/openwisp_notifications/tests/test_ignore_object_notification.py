from unittest.mock import patch

from django.db.utils import OperationalError
from django.test import TestCase
from django.utils import timezone

from openwisp_notifications import tasks
from openwisp_notifications.signals import notify
from openwisp_notifications.swapper import load_model
from openwisp_users.tests.utils import TestOrganizationMixin

from ..types import get_notification_configuration
from .test_helpers import mock_notification_types, register_notification_type

IgnoreObjectNotification = load_model("IgnoreObjectNotification")
Notification = load_model("Notification")
on_queryset = IgnoreObjectNotification.objects


class TestIgnoreObjectNotification(TestOrganizationMixin, TestCase):
    def setUp(self):
        self.obj = self._get_org_user()
        self.admin = self._get_admin()

    def test_object_notification(self):
        IgnoreObjectNotification.objects.create(
            object=self.obj, user=self.admin, valid_till=timezone.now()
        )
        # Celery task deletes it right away
        self.assertEqual(on_queryset.count(), 0)

    @patch("openwisp_notifications.tasks.delete_ignore_object_notification.apply_async")
    def test_delete_object_busy_worker(self, mocked_task):
        IgnoreObjectNotification.objects.create(
            object=self.obj, user=self.admin, valid_till=timezone.now()
        )
        self.assertEqual(on_queryset.count(), 1)

    @patch("openwisp_notifications.tasks.delete_ignore_object_notification.apply_async")
    def test_notification_for_disabled_object(self, mocked_task):
        IgnoreObjectNotification.objects.create(
            object=self.obj,
            user=self.admin,
            valid_till=(timezone.now() + timezone.timedelta(days=1)),
        )
        notify.send(sender=self.admin, type="default", target=self.obj)
        self.assertEqual(Notification.objects.count(), 0)

    @mock_notification_types
    @patch("openwisp_notifications.tasks.delete_ignore_object_notification.apply_async")
    def test_related_object_deleted(self, *args):
        type_config = get_notification_configuration("default")
        register_notification_type("test", type_config, models=[self.obj._meta.model])
        IgnoreObjectNotification.objects.create(
            object=self.obj,
            user=self.admin,
            valid_till=(timezone.now() + timezone.timedelta(days=1)),
        )
        self.obj.delete()
        self.assertEqual(on_queryset.count(), 0)

    @patch.object(
        IgnoreObjectNotification.objects, "filter", side_effect=OperationalError
    )
    def test_related_object_deleted_task(self, *args):
        tasks.delete_obsolete_objects.delay(
            self.obj._meta.app_label, self.obj._meta.model_name, self.obj.id
        )

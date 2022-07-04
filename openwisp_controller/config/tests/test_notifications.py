from unittest.mock import patch

from django.apps.registry import apps
from django.test import TransactionTestCase
from swapper import load_model

from openwisp_controller.config.tests.utils import CreateConfigMixin
from openwisp_users.tests.utils import TestOrganizationMixin

from ..signals import device_registered

Device = load_model('config', 'Device')
Notification = load_model('openwisp_notifications', 'Notification')

notification_qs = Notification.objects.all()


class TestNotifications(CreateConfigMixin, TestOrganizationMixin, TransactionTestCase):
    app_label = 'config'

    def setUp(self):
        self.admin = self._get_admin()

    def test_config_problem_notification(self):
        config = self._create_config()
        config.set_status_error()

        self.assertEqual(config.status, 'error')
        self.assertEqual(notification_qs.count(), 1)
        notification = notification_qs.first()
        self.assertEqual(notification.actor, config)
        self.assertEqual(notification.target, config.device)
        self.assertEqual(notification.type, 'config_error')
        self.assertEqual(
            notification.email_subject,
            f'[example.com] ERROR: "{config.device}"'
            ' configuration encountered an error',
        )
        self.assertIn('encountered an error', notification.message)

    def test_device_registered(self):
        # To avoid adding repetitive code for registering a device,
        # we simulate that "device_registered" signal is emitted
        config = self._create_config()
        device = config.device

        with self.subTest('is_new=True'):
            device_registered.send(sender=Device, instance=config.device, is_new=True)
            self.assertEqual(notification_qs.count(), 1)
            notification = notification_qs.first()
            self.assertEqual(notification.actor, device)
            self.assertEqual(notification.target, device)
            self.assertEqual(notification.type, 'device_registered')
            self.assertEqual(
                notification.email_subject,
                f'[example.com] SUCCESS: "{device}" registered successfully',
            )
            self.assertIn('registered successfully', notification.message)
            self.assertIn('A new device', notification.message)

        Notification.objects.all().delete()

        with self.subTest('is_new=True'):
            device_registered.send(sender=Device, instance=config.device, is_new=False)
            self.assertEqual(notification_qs.count(), 1)
            notification = notification_qs.first()
            self.assertIn('The existing device', notification.message)

    @patch('openwisp_notifications.types.NOTIFICATION_TYPES', {})
    @patch('openwisp_utils.admin_theme.dashboard.DASHBOARD_CHARTS', {})
    @patch('openwisp_utils.admin_theme.menu.MENU', {})
    def test_default_notification_type_already_unregistered(self):
        # Simulates if 'default notification type is already unregistered
        # by some other module

        # This will try to unregister 'default' notification type
        # which is already got unregistered when Django loaded.
        # No exception should be raised as the exception is already handled.
        app = apps.get_app_config(self.app_label)
        app.ready()

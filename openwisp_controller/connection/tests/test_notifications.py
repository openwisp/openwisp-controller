import os
from unittest.mock import patch

from django.apps.registry import apps
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from openwisp_notifications.signals import notify
from openwisp_notifications.types import unregister_notification_type
from swapper import load_model

from .utils import CreateConnectionsMixin

Notification = load_model('openwisp_notifications', 'Notification')
Credentials = load_model('connection', 'Credentials')
DeviceConnection = load_model('connection', 'DeviceConnection')


class BaseTestNotification:
    app_label = 'connection'

    def setUp(self):
        self._create_admin()
        self.d = self._create_device()
        self.creds = Credentials.objects.create(
            connector='openwisp_controller.connection.connectors.ssh.Ssh'
        )

    def _generic_notification_test(
        self, exp_level, exp_type, exp_verb, exp_message, exp_email_subject
    ):
        n = Notification.objects.first()
        config_app = (
            'config' if not os.environ.get('SAMPLE_APP', False) else 'sample_config'
        )
        device_url_path = reverse(f'admin:{config_app}_device_change', args=[self.d.id])
        exp_target_link = f'https://example.com{device_url_path}'

        self.assertEqual(n.type, exp_type)
        self.assertEqual(n.level, exp_level)
        self.assertEqual(n.verb, exp_verb)
        self.assertEqual(n.actor, self.d.deviceconnection_set.first())
        self.assertEqual(n.target, self.d)
        self.assertIn(exp_message.format(n=n, target_link=exp_target_link), n.message)
        self.assertEqual(n.email_subject, exp_email_subject.format(n=n))


class TestNotifications(CreateConnectionsMixin, BaseTestNotification, TestCase):
    def test_connection_is_working_none(self):
        self.assertEqual(Notification.objects.count(), 0)

        with self.subTest('no problem notification created when is_working=None'):
            DeviceConnection.objects.all().delete()
            device_connection = DeviceConnection.objects.create(
                credentials=self.creds, device=self.d, is_working=None
            )
            self.assertIsNone(device_connection.is_working)
            device_connection.is_working = False
            device_connection.save()
            self.assertEqual(Notification.objects.count(), 0)

        with self.subTest('no recovery notification created when is_working=None'):
            DeviceConnection.objects.all().delete()
            device_connection = DeviceConnection.objects.create(
                credentials=self.creds, device=self.d, is_working=None
            )
            self.assertIsNone(device_connection.is_working)
            device_connection.is_working = True
            device_connection.save()
            self.assertEqual(Notification.objects.count(), 0)

    def test_default_notification_type_already_unregistered(self):
        # Simulates if 'default notification type is already unregistered
        # by some other module

        # Unregister "config_error" and "device_registered" notification
        # types to avoid getting rasing ImproperlyConfigured exceptions
        unregister_notification_type('connection_is_not_working')
        unregister_notification_type('connection_is_working')

        # This will try to unregister 'default' notification type
        # which is already got unregistered when Django loaded.
        # No exception should be raised as the exception is already handled.
        app = apps.get_app_config(self.app_label)
        app.register_notification_types()

    @patch(
        'openwisp_controller.connection.apps.ConnectionConfig'
        '._ignore_connection_notification_reasons',
        ['Unable to connect'],
    )
    @patch.object(notify, 'send')
    def test_connection_is_working_changed_unable_to_connect(self, notify_send, *args):
        credentials = self._create_credentials_with_key(port=self.ssh_server.port)
        self._create_config(device=self.d)
        device_conn = self._create_device_connection(
            credentials=credentials, device=self.d, is_working=True
        )
        device_conn.failure_reason = (
            '[Errno None] Unable to connect to port 5555 on 127.0.0.1'
        )
        device_conn.is_working = False
        device_conn.full_clean()
        device_conn.save()
        notify_send.assert_not_called()
        # Connection makes recovery.
        device_conn.failure_reason = ''
        device_conn.is_working = True
        device_conn.full_clean()
        device_conn.save()
        notify_send.assert_not_called()


class TestNotificationTransaction(
    CreateConnectionsMixin, BaseTestNotification, TransactionTestCase
):
    def test_connection_working_notification(self):
        self.assertEqual(Notification.objects.count(), 0)
        device_connection = DeviceConnection.objects.create(
            credentials=self.creds, device=self.d, is_working=False
        )
        device_connection.is_working = True
        device_connection.save()
        self.assertEqual(Notification.objects.count(), 1)
        self._generic_notification_test(
            exp_level='info',
            exp_type='connection_is_working',
            exp_verb='working',
            exp_message=(
                '(SSH) connection to device <a href="{target_link}">'
                '{n.target}</a> is {n.verb}.'
            ),
            exp_email_subject='[example.com] RECOVERY: Connection to device {n.target}',
        )

    @patch(
        'openwisp_controller.connection.apps.ConnectionConfig'
        '._ignore_connection_notification_reasons',
        ['timed out'],
    )
    @patch.object(notify, 'send')
    def test_connection_is_working_changed_timed_out(self, notify_send, *args):
        credentials = self._create_credentials_with_key(port=self.ssh_server.port)
        self._create_config(device=self.d)
        device_conn = self._create_device_connection(
            credentials=credentials, device=self.d, is_working=True
        )
        self.assertEqual(device_conn.is_working, True)
        device_conn.is_working = False
        device_conn.failure_reason = 'timed out'
        device_conn.full_clean()
        device_conn.save()
        notify_send.assert_not_called()
        # Connection recovers, device is reachable again
        device_conn.is_working = True
        device_conn.failure_reason = ''
        device_conn.full_clean()
        device_conn.save()
        notify_send.assert_not_called()

    def test_connection_not_working_notification(self):
        device_connection = DeviceConnection.objects.create(
            credentials=self.creds, device=self.d, is_working=True
        )
        self.assertEqual(Notification.objects.count(), 0)
        device_connection.is_working = False
        device_connection.save()
        self.assertEqual(Notification.objects.count(), 1)
        self._generic_notification_test(
            exp_level='error',
            exp_type='connection_is_not_working',
            exp_verb='not working',
            exp_message=(
                '(SSH) connection to device <a href="{target_link}">'
                '{n.target}</a> is {n.verb}.'
            ),
            exp_email_subject='[example.com] PROBLEM: Connection to device {n.target}',
        )

    def test_unreachable_after_upgrade_notification(self):
        device_connection = DeviceConnection.objects.create(
            credentials=self.creds, device=self.d, is_working=True
        )
        self.assertEqual(Notification.objects.count(), 0)
        device_connection.is_working = False
        device_connection.failure_reason = (
            'Giving up, device not reachable anymore after upgrade'
        )
        device_connection.save()
        self.assertEqual(Notification.objects.count(), 1)
        self._generic_notification_test(
            exp_level='error',
            exp_type='connection_is_not_working',
            exp_verb='not working',
            exp_message=(
                '(SSH) connection to device <a href="{target_link}">'
                '{n.target}</a> is {n.verb}. '
                'Giving up, device not reachable anymore after upgrade'
            ),
            exp_email_subject='[example.com] PROBLEM: Connection to device {n.target}',
        )

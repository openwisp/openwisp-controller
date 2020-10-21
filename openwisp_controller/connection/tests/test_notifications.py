import os

from django.apps.registry import apps
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.html import strip_tags
from openwisp_notifications.types import unregister_notification_type
from swapper import load_model

from .utils import CreateConnectionsMixin

Notification = load_model('openwisp_notifications', 'Notification')
Credentials = load_model('connection', 'Credentials')
DeviceConnection = load_model('connection', 'DeviceConnection')


class TestNotifications(CreateConnectionsMixin, TestCase):
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
        url_path = reverse('notifications:notification_read_redirect', args=[n.pk])
        exp_email_link = f'https://example.com{url_path}'
        config_app = (
            'config' if not os.environ.get('SAMPLE_APP', False) else 'sample_config'
        )
        device_url_path = reverse(f'admin:{config_app}_device_change', args=[self.d.id])
        exp_target_link = f'https://example.com{device_url_path}'
        exp_email_body = '{message}' f'\n\nFor more information see {exp_email_link}.'

        email = mail.outbox.pop()
        html_message, _ = email.alternatives.pop()
        self.assertEqual(n.type, exp_type)
        self.assertEqual(n.level, exp_level)
        self.assertEqual(n.verb, exp_verb)
        self.assertEqual(n.actor, self.d.deviceconnection_set.first())
        self.assertEqual(n.target, self.d)
        self.assertEqual(
            n.message, exp_message.format(n=n, target_link=exp_target_link)
        )
        self.assertEqual(
            n.email_subject, exp_email_subject.format(n=n),
        )
        self.assertEqual(email.subject, n.email_subject)
        self.assertEqual(
            email.body, exp_email_body.format(message=strip_tags(n.message))
        )
        self.assertIn(
            f'<a href="{exp_email_link}">'
            f'For further information see "device: {n.target}".</a>',
            html_message,
        )

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
                '<p>(SSH) connection to device <a href="{target_link}">'
                '{n.target}</a> is {n.verb}. </p>'
            ),
            exp_email_subject='[example.com] RECOVERY: Connection to device {n.target}',
        )

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
                '<p>(SSH) connection to device <a href="{target_link}">'
                '{n.target}</a> is {n.verb}. </p>'
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
                '<p>(SSH) connection to device <a href="{target_link}">'
                '{n.target}</a> is {n.verb}. '
                'Giving up, device not reachable anymore after upgrade</p>'
            ),
            exp_email_subject='[example.com] PROBLEM: Connection to device {n.target}',
        )

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

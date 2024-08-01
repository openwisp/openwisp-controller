from unittest.mock import patch

from celery.exceptions import Retry
from django.apps.registry import apps
from django.conf import settings
from django.test import TransactionTestCase
from requests.exceptions import RequestException
from swapper import load_model

from openwisp_controller.config.tests.utils import (
    CreateConfigMixin,
    TestZeroTierVpnMixin,
)

from ..settings import API_TASK_RETRY_OPTIONS
from ..signals import device_registered

Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')
Notification = load_model('openwisp_notifications', 'Notification')

notification_qs = Notification.objects.all()


class TestNotifications(
    CreateConfigMixin,
    TestZeroTierVpnMixin,
    TransactionTestCase,
):
    app_label = 'config'
    _ZT_SERVICE_REQUESTS = 'openwisp_controller.config.api.zerotier_service.requests'
    _ZT_API_TASKS_INFO_LOGGER = 'openwisp_controller.config.tasks_zerotier.logger.info'
    _ZT_API_TASKS_WARN_LOGGER = 'openwisp_controller.config.tasks_zerotier.logger.warn'
    _ZT_API_TASKS_ERR_LOGGER = 'openwisp_controller.config.tasks_zerotier.logger.error'
    # As the locmem cache does not support the redis backend cache.keys() method
    _ZT_API_TASKS_LOCMEM_CACHE_KEYS = f"{settings.CACHES['default']['BACKEND']}.keys"

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
        self.assertEqual(notification.target_url.endswith('#config-group'), True)

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

    @patch(_ZT_API_TASKS_LOCMEM_CACHE_KEYS, create=True)
    @patch(_ZT_API_TASKS_ERR_LOGGER)
    @patch(_ZT_API_TASKS_WARN_LOGGER)
    @patch(_ZT_API_TASKS_INFO_LOGGER)
    @patch(_ZT_SERVICE_REQUESTS)
    def test_zerotier_api_tasks_notification(
        self,
        mock_requests,
        mock_info,
        mock_warn,
        mock_error,
        mock_locmem_cache_keys,
    ):
        mock_requests.get.side_effect = [
            # For node status
            self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
        ]
        mock_requests.post.side_effect = [
            # For create network
            self._get_mock_response(200),
            # For controller network join
            self._get_mock_response(200),
            # For controller auth and ip assignment
            self._get_mock_response(200),
        ]
        mock_locmem_cache_keys.return_value = ['test_zt_api_tasks_notification_key']
        vpn = self._create_zerotier_vpn()
        self.assertEqual(Vpn.objects.count(), 1)
        notification_qs = Notification.objects.all()
        # Make sure no notification is generated
        # for the vpn server creation
        self.assertEqual(notification_qs.count(), 0)
        self.assertEqual(mock_info.call_count, 2)
        mock_info.reset_mock()
        mock_requests.reset_mock()

        with self.subTest(
            'Test no notifications are generated for the vpn server update'
        ):
            mock_requests.get.side_effect = [
                # For node status
                self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
            ]
            mock_requests.post.side_effect = [
                # For update network
                self._get_mock_response(200),
                # For controller auth and ip assignment
                self._get_mock_response(200),
            ]
            # Let's update the vpn config
            config = vpn.get_config()['zerotier'][0]
            config.update({'private': True})
            vpn.full_clean()
            vpn.save()
            self.assertEqual(mock_info.call_count, 2)
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_error.call_count, 0)
            self.assertEqual(notification_qs.count(), 0)
        mock_info.reset_mock()
        mock_requests.reset_mock()

        with self.subTest(
            (
                'Test no notifications are generated for '
                'the vpn server api tasks (retry mechanism)'
            )
        ), patch('celery.app.task.Task.request') as mock_task_request:
            max_retries = API_TASK_RETRY_OPTIONS.get('max_retries')
            mock_task_request.called_directly = False
            config = vpn.get_config()['zerotier'][0]
            config.update({'private': True})

            with self.subTest(
                'Test notification when update when max retry limit is not reached'
            ), self.assertRaises(Retry):
                mock_requests.get.side_effect = [
                    # For node status
                    self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
                ]
                mock_requests.post.side_effect = [
                    # For update network
                    self._get_mock_response(200),
                    # For controller auth and ip assignment
                    # (internal server error)
                    self._get_mock_response(
                        500,
                        response={},
                        exc=RequestException,
                    ),
                ]
                # Second last retry attempt (4th)
                mock_task_request.retries = max_retries - 1
                vpn.full_clean()
                vpn.save()
            self.assertEqual(mock_info.call_count, 1)
            # Ensure that it logs with the 'warning' level
            self.assertEqual(mock_warn.call_count, 1)
            self.assertEqual(mock_error.call_count, 0)
            self.assertEqual(notification_qs.count(), 0)
            mock_info.reset_mock()
            mock_warn.reset_mock()
            mock_requests.reset_mock()

            with self.subTest(
                'Test notification when update when max retry limit is reached'
            ), self.assertRaises(RequestException):
                mock_requests.get.side_effect = [
                    # For node status
                    self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
                ]
                mock_requests.post.side_effect = [
                    # For update network
                    self._get_mock_response(200),
                    # For controller auth and ip assignment
                    # (internal server error)
                    self._get_mock_response(
                        500,
                        response={},
                        exc=RequestException,
                    ),
                ]
                # Last retry attempt (5th)
                mock_task_request.retries = max_retries
                vpn.full_clean()
                vpn.save()
            self.assertEqual(mock_info.call_count, 1)
            self.assertEqual(mock_warn.call_count, 0)
            # Ensure that it logs last attempt with the 'error' level
            self.assertEqual(mock_error.call_count, 1)
            self.assertEqual(notification_qs.count(), 0)
            mock_info.reset_mock()
            mock_error.reset_mock()
            mock_requests.reset_mock()

        with self.subTest(
            'Test notifications are generated for API tasks (unrecoverable errors)'
        ):
            with self.subTest(
                'Test error notification on failure of first call (update network)'
            ):
                # mock_get.return_value = None
                mock_requests.get.side_effect = [
                    # For node status
                    self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
                ]
                mock_requests.post.side_effect = [
                    # During an update network failure (bad request)
                    # the task will not perform the update network member operation
                    # and cache.get(task_key) will be 'None'
                    self._get_mock_response(
                        400,
                        response={'message': 'body JSON is invalid'},
                        exc=RequestException,
                    ),
                ]
                config = vpn.get_config()['zerotier'][0]
                config.update({'private': True})
                vpn.full_clean()
                vpn.save()
                self.assertEqual(mock_info.call_count, 0)
                self.assertEqual(mock_warn.call_count, 0)
                # For unrecoverable error
                self.assertEqual(mock_error.call_count, 1)
                self.assertEqual(notification_qs.count(), 1)
                notification = notification_qs.first()
                self.assertEqual(notification.actor, vpn)
                self.assertEqual(notification.target, vpn)
                self.assertEqual(notification.type, 'api_task_error')
                self.assertIn(
                    'Unable to perform update operation', notification.message
                )

            mock_info.reset_mock()
            mock_error.reset_mock()
            mock_requests.reset_mock()
            notification_qs.delete()

            with self.subTest(
                (
                    'Test recovery notification on first call (update network)'
                    'and error notification on second call (update network member)'
                )
            ):
                mock_requests.get.side_effect = [
                    # For node status
                    self._get_mock_response(200, response=self._TEST_ZT_NODE_CONFIG)
                ]
                mock_requests.post.side_effect = [
                    # For update network
                    self._get_mock_response(200),
                    # For controller auth and ip assignment
                    # (bad request)
                    self._get_mock_response(
                        400,
                        response={},
                        exc=RequestException,
                    ),
                ]
                config = vpn.get_config()['zerotier'][0]
                config.update({'private': True})
                vpn.full_clean()
                vpn.save()
                self.assertEqual(notification_qs.count(), 2)
                # For successful network update
                notification_error = notification_qs.first()
                notification_recovery = notification_qs.last()
                self.assertEqual(mock_info.call_count, 1)
                self.assertEqual(notification_recovery.actor, vpn)
                self.assertEqual(notification_recovery.target, vpn)
                self.assertEqual(notification_recovery.type, 'api_task_recovery')
                self.assertIn('The update operation on', notification_recovery.message)
                # For unrecoverable error
                self.assertEqual(mock_warn.call_count, 0)
                self.assertEqual(mock_error.call_count, 1)
                self.assertEqual(notification_error.actor, vpn)
                self.assertEqual(notification_error.target, vpn)
                self.assertEqual(notification_error.type, 'api_task_error')
                self.assertIn(
                    'Unable to perform update member operation',
                    notification_error.message,
                )

            mock_info.reset_mock()
            mock_error.reset_mock()
            mock_requests.reset_mock()
            notification_qs.delete()

        with self.subTest('Test no notifications are generated for vpn deletion'):
            mock_requests.delete.side_effect = [
                # For delete network
                self._get_mock_response(200, response={}),
                # For controller leave network
                self._get_mock_response(200, response={}),
            ]
            vpn.delete()
            self.assertEqual(Vpn.objects.count(), 0)
            # Only logging for vpn deletion & leave network
            self.assertEqual(mock_info.call_count, 2)
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_error.call_count, 0)
            self.assertEqual(notification_qs.count(), 0)

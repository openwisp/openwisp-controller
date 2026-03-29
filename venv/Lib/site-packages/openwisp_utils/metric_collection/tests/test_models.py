from datetime import datetime, timezone
from unittest.mock import patch

import requests
from django.apps import apps
from django.db import migrations
from django.test import TestCase, override_settings
from freezegun import freeze_time
from openwisp_utils import utils
from openwisp_utils.admin_theme import system_info
from urllib3.response import HTTPResponse

from .. import helper, models, tasks
from ..models import Consent, OpenwispVersion
from . import (
    _ENABLED_OPENWISP_MODULES_RETURN_VALUE,
    _HEARTBEAT_METRICS,
    _MODULES_UPGRADE_EXPECTED_METRICS,
    _NEW_INSTALLATION_METRICS,
    _OS_DETAILS_RETURN_VALUE,
)


class TestOpenwispVersion(TestCase):
    def setUp(self):
        # The post_migrate signal creates the first OpenwispVersion object
        # and uses the actual modules installed in the Python environment.
        # This would cause tests to fail when other modules are also installed.
        OpenwispVersion.objects.update(
            module_version={
                "OpenWISP Version": "23.0.0a",
                **_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
            },
            created=datetime.strptime(
                "2023-11-01 00:00:00", "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=timezone.utc),
        )

    @patch(
        "openwisp_utils.admin_theme.system_info.import_string", side_effect=ImportError
    )
    def test_installation_method_not_defined(self, *args):
        self.assertEqual(system_info.get_openwisp_installation_method(), "unspecified")

    def test_log_module_version_changes_on_new_installation(
        self,
    ):
        OpenwispVersion.objects.all().delete()
        is_install, is_upgrade = OpenwispVersion.log_module_version_changes(
            system_info.get_enabled_openwisp_modules()
        )
        self.assertEqual(
            is_install,
            True,
        )
        self.assertEqual(is_upgrade, False)

    @patch.object(models, "get_openwisp_version", return_value="23.0.0a")
    @patch.object(
        models,
        "get_enabled_openwisp_modules",
        return_value=_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
    )
    @patch.object(
        models,
        "get_os_details",
        return_value=_OS_DETAILS_RETURN_VALUE,
    )
    @patch("openwisp_utils.metric_collection.models.post_metrics")
    @freeze_time("2023-12-01 00:00:00")
    def test_new_installation(self, mocked_post, *args):
        OpenwispVersion.objects.all().delete()
        tasks.send_usage_metrics.delay(category="Install")
        mocked_post.assert_called_with(_NEW_INSTALLATION_METRICS)
        self.assertEqual(OpenwispVersion.objects.count(), 1)
        version = OpenwispVersion.objects.first()
        expected_module_version = {
            "OpenWISP Version": "23.0.0a",
            **_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
        }
        self.assertEqual(version.module_version, expected_module_version)

    @patch.object(models, "get_openwisp_version", return_value="23.0.0a")
    @patch.object(
        models,
        "get_enabled_openwisp_modules",
        return_value=_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
    )
    @patch.object(
        models,
        "get_os_details",
        return_value=_OS_DETAILS_RETURN_VALUE,
    )
    @patch("openwisp_utils.metric_collection.models.post_metrics")
    @freeze_time("2023-12-01 00:00:00")
    def test_install_detected_on_heartbeat_event(self, mocked_post, *args):
        OpenwispVersion.objects.all().delete()
        tasks.send_usage_metrics.delay(category="Heartbeat")
        mocked_post.assert_called_with(_NEW_INSTALLATION_METRICS)
        self.assertEqual(OpenwispVersion.objects.count(), 1)
        version = OpenwispVersion.objects.first()
        expected_module_version = {
            "OpenWISP Version": "23.0.0a",
            **_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
        }
        self.assertEqual(version.module_version, expected_module_version)

    @patch.object(models, "get_openwisp_version", return_value="23.0.0a")
    @patch.object(
        models,
        "get_enabled_openwisp_modules",
        return_value=_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
    )
    @patch.object(
        models,
        "get_os_details",
        return_value=_OS_DETAILS_RETURN_VALUE,
    )
    @patch("openwisp_utils.metric_collection.models.post_metrics")
    @freeze_time("2023-12-01 00:00:00")
    def test_install_not_detected_on_install_event(self, mocked_post, *args):
        # Checks when the send_usage_metrics is triggered
        # with "Install" category, but there's no actual upgrade.
        self.assertEqual(OpenwispVersion.objects.count(), 1)
        tasks.send_usage_metrics(category="Install")
        mocked_post.assert_not_called()

    @patch.object(models, "get_openwisp_version", return_value="23.0.0a")
    @patch.object(
        models,
        "get_enabled_openwisp_modules",
        return_value=_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
    )
    @patch.object(
        models,
        "get_os_details",
        return_value=_OS_DETAILS_RETURN_VALUE,
    )
    @patch("openwisp_utils.metric_collection.models.post_metrics")
    @freeze_time("2023-12-01 00:00:00")
    def test_heartbeat(self, mocked_post, *args):
        expected_module_version = {
            "OpenWISP Version": "23.0.0a",
            **_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
            **_OS_DETAILS_RETURN_VALUE,
        }
        OpenwispVersion.objects.update(module_version=expected_module_version)
        self.assertEqual(OpenwispVersion.objects.count(), 1)
        tasks.send_usage_metrics.delay()
        mocked_post.assert_called_with(_HEARTBEAT_METRICS)
        self.assertEqual(OpenwispVersion.objects.count(), 1)
        version = OpenwispVersion.objects.first()
        self.assertEqual(version.module_version, expected_module_version)

    @patch.object(models, "get_openwisp_version", return_value="23.0.0a")
    @patch.object(
        models,
        "get_enabled_openwisp_modules",
        return_value=_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
    )
    @patch.object(
        models,
        "get_os_details",
        return_value=_OS_DETAILS_RETURN_VALUE,
    )
    @patch("openwisp_utils.metric_collection.models.post_metrics")
    @freeze_time("2023-12-01 00:00:00")
    def test_modules_upgraded(self, mocked_post, *args):
        self.assertEqual(OpenwispVersion.objects.count(), 1)
        OpenwispVersion.objects.update(
            module_version={
                "OpenWISP Version": "22.10.0",
                "openwisp-utils": "1.0.5",
                "openwisp-users": "1.0.2",
            }
        )
        tasks.send_usage_metrics.delay(category="Upgrade")
        mocked_post.assert_called_with(_MODULES_UPGRADE_EXPECTED_METRICS)

        self.assertEqual(OpenwispVersion.objects.count(), 2)
        version = OpenwispVersion.objects.first()
        expected_module_version = {
            "OpenWISP Version": "23.0.0a",
            **_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
        }
        self.assertEqual(version.module_version, expected_module_version)

    @patch.object(models, "get_openwisp_version", return_value="23.0.0a")
    @patch.object(
        models,
        "get_enabled_openwisp_modules",
        return_value=_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
    )
    @patch.object(
        models,
        "get_os_details",
        return_value=_OS_DETAILS_RETURN_VALUE,
    )
    @patch("openwisp_utils.metric_collection.models.post_metrics")
    @freeze_time("2023-12-01 00:00:00")
    def test_upgrade_detected_on_heartbeat_event(self, mocked_post, *args):
        self.assertEqual(OpenwispVersion.objects.count(), 1)
        OpenwispVersion.objects.update(
            module_version={
                "OpenWISP Version": "22.10.0",
                "openwisp-utils": "1.0.5",
                "openwisp-users": "1.0.2",
            }
        )
        tasks.send_usage_metrics.delay(category="Heartbeat")
        mocked_post.assert_called_with(_MODULES_UPGRADE_EXPECTED_METRICS)

        self.assertEqual(OpenwispVersion.objects.count(), 2)
        version = OpenwispVersion.objects.first()
        expected_module_version = {
            "OpenWISP Version": "23.0.0a",
            **_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
        }
        self.assertEqual(version.module_version, expected_module_version)

    @patch.object(models, "get_openwisp_version", return_value="23.0.0a")
    @patch.object(
        models,
        "get_enabled_openwisp_modules",
        return_value=_ENABLED_OPENWISP_MODULES_RETURN_VALUE,
    )
    @patch.object(
        models,
        "get_os_details",
        return_value=_OS_DETAILS_RETURN_VALUE,
    )
    @patch("openwisp_utils.metric_collection.models.post_metrics")
    @freeze_time("2023-12-01 00:00:00")
    def test_upgrade_not_detected_on_upgrade_event(self, mocked_post, *args):
        """Tests send_usage_metrics is triggered with "Upgrade" category but no modules were upgraded."""
        self.assertEqual(OpenwispVersion.objects.count(), 1)
        tasks.send_usage_metrics.delay(category="Upgrade")
        mocked_post.assert_not_called()

    @patch("time.sleep")
    @patch("logging.Logger.warning")
    @patch("logging.Logger.error")
    def test_post_usage_metrics_400_response(self, mocked_error, mocked_warning, *args):
        bad_response = requests.Response()
        bad_response.status_code = 400
        with patch.object(
            helper, "retryable_request", return_value=bad_response
        ) as mocked_retryable_request:
            tasks.send_usage_metrics.delay()
        mocked_retryable_request.assert_called_once()
        mocked_warning.assert_not_called()
        mocked_error.assert_called_with(
            "Collection of usage metrics failed, max retries exceeded."
            " Error: HTTP 400 Response"
        )

    @patch("urllib3.util.retry.Retry.sleep")
    @patch(
        "urllib3.connectionpool.HTTPConnection.request",
    )
    @patch(
        "urllib3.connectionpool.HTTPConnection.getresponse",
        return_value=HTTPResponse(status=500, version="1.1"),
    )
    @patch("logging.Logger.error")
    def test_post_usage_metrics_500_response(
        self, mocked_error, mocked_getResponse, *args
    ):
        # Unmock post request from MockedRequestPostRunner
        with patch.object(
            utils.requests.Session, "post", new=utils.requests.Session._original_post
        ):
            tasks.send_usage_metrics.delay()
        self.assertEqual(len(mocked_getResponse.mock_calls), 11)
        mocked_error.assert_called_with(
            "Collection of usage metrics failed, max retries exceeded."
            " Error: HTTPSConnectionPool(host='analytics.openwisp.io', port=443):"
            " Max retries exceeded with url: /cleaninsights.php (Caused by ResponseError"
            "('too many 500 error responses'))"
        )

    @patch("time.sleep")
    @patch("logging.Logger.warning")
    @patch("logging.Logger.error")
    def test_post_usage_metrics_204_response(self, mocked_error, mocked_warning, *args):
        success_response = requests.Response()
        success_response.status_code = 204
        with patch.object(
            helper, "retryable_request", return_value=success_response
        ) as mocked_retryable_request:
            tasks.send_usage_metrics.delay()
        self.assertEqual(len(mocked_retryable_request.mock_calls), 1)
        mocked_warning.assert_not_called()
        mocked_error.assert_not_called()

    @patch("urllib3.util.retry.Retry.sleep")
    @patch(
        "urllib3.connectionpool.HTTPConnection.request",
    )
    @patch(
        "urllib3.connectionpool.HTTPConnectionPool._get_conn",
        side_effect=OSError,
    )
    @patch("logging.Logger.error")
    def test_post_usage_metrics_connection_error(
        self, mocked_error, mocked_get_conn, *args
    ):
        # Unmock post request from MockedRequestPostRunner
        with patch.object(
            utils.requests.Session, "post", new=utils.requests.Session._original_post
        ):
            tasks.send_usage_metrics.delay()
        mocked_error.assert_called_with(
            "Collection of usage metrics failed, max retries exceeded."
            " Error: HTTPSConnectionPool(host='analytics.openwisp.io', port=443):"
            " Max retries exceeded with url: /cleaninsights.php"
            " (Caused by ProtocolError('Connection aborted.', OSError()))"
        )
        self.assertEqual(mocked_get_conn.call_count, 11)

    @patch.object(tasks.send_usage_metrics, "delay")
    def test_post_migrate_receiver(self, mocked_task, *args):
        app = apps.get_app_config("metric_collection")

        with self.subTest(
            "Test task iRs called for checking upgrades when plan is empty"
        ):
            app.post_migrate_receiver(plan=[])
            mocked_task.assert_called_with(category="Upgrade")
        mocked_task.reset_mock()

        with self.subTest(
            "Test task is called for checking upgrades "
            "when first migration in plan is not for ContentTypes"
        ):
            app.post_migrate_receiver(
                plan=[
                    (
                        migrations.Migration(
                            name="0001_initial", app_label="openwisp_users"
                        ),
                        False,
                    )
                ]
            )
            mocked_task.assert_called_with(category="Upgrade")
        mocked_task.reset_mock()
        plan = [
            (
                migrations.Migration(name="0001_initial", app_label="contenttypes"),
                False,
            )
        ]

        with self.subTest(
            "Test task called when first migration in plan is for ContentTypes"
        ):
            app.post_migrate_receiver(plan=plan)
            mocked_task.assert_called_with(category="Install")
        mocked_task.reset_mock()

        with self.subTest("Test task not called in development"):
            with override_settings(DEBUG=True):
                app.post_migrate_receiver(plan=plan)
            mocked_task.assert_not_called()

    @patch("openwisp_utils.metric_collection.models.post_metrics")
    def test_send_usage_metrics_user_opted_out(self, mocked_post_usage_metrics):
        Consent.objects.create(user_consented=False)
        tasks.send_usage_metrics.delay()
        mocked_post_usage_metrics.assert_not_called()

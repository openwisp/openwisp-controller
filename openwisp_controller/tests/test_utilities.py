from unittest.mock import patch

from django.test import TestCase, override_settings

from .. import checks, context_processors
from .. import settings as app_settings
from . import _get_updated_templates_settings


class TestUtilities(TestCase):
    def test_cors_configutation_check(self):
        error_message = '"django-cors-headers" is either not installed or improperly'

        def run_check():
            return checks.check_cors_configuration(None).pop()

        with self.subTest('Test OPENWISP_CONTROLLER_API_HOST not set'):
            error = checks.check_cors_configuration(None)
            self.assertEqual(len(error), 0)

        with patch.object(
            app_settings,
            'OPENWISP_CONTROLLER_API_HOST',
            'https://example.com',
        ):
            with self.subTest('Test "django-cors-headers" absent in INSTALLED_APPS'):
                error = run_check()
                self.assertIn(error_message, error.hint)

            with self.subTest('Test "django-cors-headers" middleware not configured'):
                error = run_check()
                self.assertIn(error_message, error.hint)

    def test_openwisp_controller_context_processor_check(self):
        def runcheck():
            return checks.check_openwisp_controller_ctx_processor(None).pop()

        with self.subTest('Test OPENWISP_CONTROLLER_API_HOST not set'):
            error = checks.check_openwisp_controller_ctx_processor(None)
            self.assertEqual(len(error), 0)

        with self.subTest('Test OPENWISP_CONTROLLER_API_HOST configured'):
            with patch.object(
                app_settings,
                'OPENWISP_CONTROLLER_API_HOST',
                'https://example.com',
            ):
                error_message = 'absent from context processor'
                error = runcheck()
                self.assertIn(error_message, error.hint)

    @patch.object(
        app_settings,
        'OPENWISP_CONTROLLER_API_HOST',
        'https://example.com',
    )
    def test_openwisp_controller_context_processor(self):
        with override_settings(TEMPLATES=_get_updated_templates_settings()):
            context = {
                'OPENWISP_CONTROLLER_API_HOST': 'https://example.com',
            }
            self.assertEqual(context_processors.controller_api_settings(None), context)

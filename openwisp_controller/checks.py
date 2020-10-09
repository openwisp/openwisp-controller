from django.conf import settings
from django.core import checks

from . import settings as app_settings


def check_cors_configuration(app_configs, **kwargs):
    errors = []
    if not app_settings.OPENWISP_CONTROLLER_API_HOST:
        return errors

    if not (
        'corsheaders' in settings.INSTALLED_APPS
        and 'corsheaders.middleware.CorsMiddleware' in settings.MIDDLEWARE
    ):
        errors.append(
            checks.Warning(
                msg='Improperly Configured',
                hint=(
                    '"django-cors-headers" is either not installed or improperly '
                    'configured. CORS configuration is required for using '
                    '"OPENWISP_CONTROLLER_API_HOST" settings. '
                    ' Configure equivalent CORS rules on your server '
                    'if you are not using "django-cors-headers".'
                ),
                obj='Settings',
            )
        )
    return errors


def check_openwisp_controller_ctx_processor(app_config, **kwargs):
    errors = []
    ctx_processor = 'openwisp_controller.context_processors.controller_api_settings'

    if not app_settings.OPENWISP_CONTROLLER_API_HOST:
        return errors

    if not (ctx_processor in settings.TEMPLATES[0]['OPTIONS']['context_processors']):
        errors.append(
            checks.Warning(
                msg='Improperly Configured',
                hint=(
                    f'"{ctx_processor} is absent from context processors.'
                    'It is required to be added in TEMPLATES["context_processor"] '
                    'for "OPENWISP_CONTROLLER_API_HOST" to work properly.'
                ),
                obj='Settings',
            )
        )
    return errors

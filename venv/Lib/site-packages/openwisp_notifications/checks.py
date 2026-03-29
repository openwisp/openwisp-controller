from django.conf import settings
from django.contrib.admin import ModelAdmin
from django.core import checks
from django.utils.module_loading import import_string

from openwisp_notifications import settings as app_settings


@checks.register
def check_cors_configuration(app_configs, **kwargs):
    errors = []
    if not app_settings.HOST:
        return errors

    if not (
        "corsheaders" in settings.INSTALLED_APPS
        and "corsheaders.middleware.CorsMiddleware" in settings.MIDDLEWARE
    ):
        errors.append(
            checks.Warning(
                msg="Improperly Configured",
                hint=(
                    '"django-cors-headers" is either not installed or improperly configured.'
                    ' CORS configuration is required for using "OPENWISP_NOTIFICATIONS_HOST" settings.'
                    " Configure equivalent CORS rules on your server if you are not using"
                    ' "django-cors-headers".'
                ),
                obj="Settings",
            )
        )
    return errors


@checks.register
def check_ow_object_notification_widget_setting(app_configs, **kwargs):
    errors = []
    if not isinstance(app_settings.IGNORE_ENABLED_ADMIN, list):
        errors.append(
            checks.Warning(
                msg="Improperly Configured",
                hint=(
                    '"OPENWISP_NOTIFICATIONS_IGNORE_ENABLED_ADMIN" should be a list, '
                    f"{type(app_settings.IGNORE_ENABLED_ADMIN)} provided"
                ),
                obj="Settings",
            )
        )
        return errors

    # Check individual entries of IGNORE_ENABLED_ADMIN
    for path in app_settings.IGNORE_ENABLED_ADMIN:
        if not isinstance(path, str):
            errors.append(
                checks.Error(
                    msg="Improperly Configured",
                    hint=(
                        '"OPENWISP_NOTIFICATIONS_IGNORE_ENABLED_ADMIN" should contain '
                        f"dotted path string to ModelAdmin, found {type(path)}"
                    ),
                    obj="Settings",
                )
            )
            continue
        # Check whether dotted path points to subclass of ModelAdmin class
        try:
            model_admin_cls = import_string(path)
            assert issubclass(model_admin_cls, ModelAdmin)
        except ImportError:
            errors.append(
                checks.Error(
                    msg="Improperly Configured",
                    hint=(
                        f'Failed to import "{path}" defined in '
                        '"OPENWISP_NOTIFICATIONS_IGNORE_ENABLED_ADMIN". '
                        "Make sure you have provided a valid dotted path."
                    ),
                    obj="Settings",
                )
            )
        except AssertionError:
            errors.append(
                checks.Error(
                    msg="Improperly Configured",
                    hint=(
                        f'"{path}" does not subclasses '
                        '"django.contrib.admin.ModelAdmin". Only derivatives '
                        'ModelAdmin can be added in "OPENWISP_NOTIFICATIONS_IGNORE_ENABLED_ADMIN".'
                    ),
                    obj="Settings",
                )
            )
    return errors

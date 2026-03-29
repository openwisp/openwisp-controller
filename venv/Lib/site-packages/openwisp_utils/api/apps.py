from django.apps import AppConfig
from django.conf import settings

from ..utils import deep_merge_dicts, default_or_test

DEFAULT_REST_FRAMEWORK_SETTINGS = {
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": default_or_test(value="40/hour", test=None)},
}


class ApiAppConfig(AppConfig):
    API_ENABLED = False

    def ready(self, *args, **kwargs):
        if self.api_enabled:
            self.configure_rest_framework_defaults()

    @property
    def api_enabled(self):
        return "rest_framework" in settings.INSTALLED_APPS and self.API_ENABLED

    def configure_rest_framework_defaults(self):
        # merge the default DRF settings defined in openwisp-utils
        # and the default DRF settings defined in the app inheriting this class
        default_settings = DEFAULT_REST_FRAMEWORK_SETTINGS
        app_settings = getattr(self, "REST_FRAMEWORK_SETTINGS", {})
        merged_default_settings = deep_merge_dicts(default_settings, app_settings)
        # get the DRF settings defined in settings.py, if any
        current_settings = getattr(settings, "REST_FRAMEWORK", {})

        # loop over the default settings dict
        for key, value in merged_default_settings.items():
            # if any key is a dictionary, and the same key
            # is also defined in settings.py
            # merge the two dicts, giving precedence
            # to what is defined in settings.py
            if isinstance(value, dict) and key in current_settings:
                value.update(current_settings[key])
                current_settings[key] = value
                continue
            # otherwise just set it as default value
            current_settings.setdefault(key, value)

        # explicitly set it in settings.py
        setattr(settings, "REST_FRAMEWORK", current_settings)

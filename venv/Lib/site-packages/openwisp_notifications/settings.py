import re

from django.conf import settings

CONFIG_DEFAULTS = {
    "PAGINATE_BY": 20,
    "SOFT_DELETE": False,
    "NUM_TO_FETCH": 10,
    "CACHE_TIMEOUT": 2,
}
DISALLOW_PREFERENCES_CHANGE_TYPE = ["generic_message"]


def get_setting(name, default=None):
    """
    Get a setting from the Django settings module or return a default value.
    """
    return getattr(settings, f"OPENWISP_NOTIFICATIONS_{name}", default)


HOST = get_setting("HOST", None)

CACHE_TIMEOUT = get_setting("CACHE_TIMEOUT", 2 * 24 * 60 * 60)  # 2 days

IGNORE_ENABLED_ADMIN = get_setting("IGNORE_ENABLED_ADMIN", [])
POPULATE_PREFERENCES_ON_MIGRATE = get_setting("POPULATE_PREFERENCES_ON_MIGRATE", True)
NOTIFICATION_STORM_PREVENTION = get_setting(
    "NOTIFICATION_STORM_PREVENTION",
    {
        "short_term_time_period": 10,
        "short_term_notification_count": 6,
        "long_term_time_period": 180,
        "long_term_notification_count": 30,
        "initial_backoff": 1,
        "backoff_increment": 1,
        "max_allowed_backoff": 15,
    },
)

SOUND = get_setting("SOUND", "openwisp-notifications/audio/notification_bell.mp3")

WEB_ENABLED = get_setting("WEB_ENABLED", True)
EMAIL_ENABLED = get_setting("EMAIL_ENABLED", True)
EMAIL_BATCH_INTERVAL = get_setting("EMAIL_BATCH_INTERVAL", 180 * 60)  # 3 hours
EMAIL_BATCH_DISPLAY_LIMIT = get_setting("EMAIL_BATCH_DISPLAY_LIMIT", 15)


# Remove the leading "/static/" here as it will
# conflict with the "static()" call in context_processors.py.
# This is done for backward compatibility.
SOUND = re.sub("^/static/", "", SOUND)


def get_config():
    user_config = get_setting("CONFIG", {})
    config = CONFIG_DEFAULTS.copy()
    config.update(user_config)
    return config

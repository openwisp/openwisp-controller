from rest_framework.throttling import AnonRateThrottle

from openwisp_users import settings as app_settings


class AuthRateThrottle(AnonRateThrottle):
    rate = app_settings.USERS_AUTH_THROTTLE_RATE

from django.conf import settings

EXTENDED_APPS = getattr(settings, "EXTENDED_APPS", [])

# API settings
API_DOCS = getattr(settings, "OPENWISP_API_DOCS", True)
API_INFO = getattr(
    settings,
    "OPENWISP_API_INFO",
    {
        "title": "OpenWISP API",
        "default_version": "v1",
        "description": "OpenWISP REST API",
    },
)

CELERY_HARD_TIME_LIMIT = getattr(settings, "OPENWISP_CELERY_HARD_TIME_LIMIT", 120)
CELERY_SOFT_TIME_LIMIT = getattr(settings, "OPENWISP_CELERY_SOFT_TIME_LIMIT", 30)

from django.conf import settings


def get_setting(option, default):
    return getattr(settings, f"OPENWISP_CONTROLLER_{option}", default)


OPENWISP_CONTROLLER_API_HOST = get_setting("API_HOST", None)

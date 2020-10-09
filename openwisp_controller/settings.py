from django.conf import settings

OPENWISP_CONTROLLER_API_HOST = getattr(settings, 'OPENWISP_CONTROLLER_API_HOST', None)

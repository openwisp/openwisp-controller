from django.conf import settings
from django.conf.urls import include, url

url_metadata = [
    # allauth proxy
    {
        'regexp': r'^accounts/',
        'app': 'openwisp_users',
        'include': {'module': 'openwisp_users.accounts.urls'},
    },
    # openwisp_notifications
    {
        'regexp': '',
        'app': 'openwisp_notifications',
        'include': {'module': 'openwisp_notifications.urls'},
    },
    # openwisp_ipam
    {
        'regexp': '',
        'app': 'openwisp_ipam',
        'include': {'module': 'openwisp_ipam.urls'},
    },
    # openwisp_controller.pki (CRL view)
    {
        'regexp': r'^',
        'app': 'openwisp_controller.pki',
        'include': {'module': '{app}.urls', 'namespace': 'x509'},
    },
    # openwisp_controller.pki.api
    {
        'regexp': r'^api/v1/',
        'app': 'openwisp_controller.pki',
        'include': {'module': '{app}.api.urls', 'namespace': 'pki_api'},
    },
    # openwisp_controller controller
    {
        'regexp': r'^',
        'app': 'openwisp_controller.config',
        'include': {'module': '{app}.controller.urls', 'namespace': 'controller'},
    },
    # owm_legacy
    {
        'regexp': r'^',
        'app': 'owm_legacy',
        'include': {'module': '{app}.urls', 'namespace': 'owm'},
    },
    # openwisp_controller.geo
    {
        'regexp': r'^',
        'app': 'openwisp_controller.geo',
        'include': {'module': '{app}.api.urls', 'namespace': 'geo_api'},
    },
    # openwisp_controller.config
    {
        'regexp': r'^',
        'app': 'openwisp_controller.config',
        'include': {'module': '{app}.urls', 'namespace': 'config'},
    },
    # openwisp_controller.config.api
    {
        'regexp': r'^api/v1/',
        'app': 'openwisp_controller.config',
        'include': {'module': '{app}.api.urls', 'namespace': 'config_api'},
    },
    # openwisp_controller.connection
    {
        'regexp': r'^',
        'app': 'openwisp_controller.connection',
        'include': {'module': '{app}.api.urls', 'namespace': 'connection_api'},
    },
]

urlpatterns = []

for meta in url_metadata:
    module = meta['include'].pop('module')
    if 'app' in meta:
        # if app attribute is specified, ensure the app is installed, or skip otherwise
        # this allows some flexibility during development or when trying custom setups
        if meta['app'] not in settings.INSTALLED_APPS:
            continue
        # DRY python module path
        module = module.format(**meta)
    urlpatterns.append(url(meta['regexp'], include(module, **meta['include'])))

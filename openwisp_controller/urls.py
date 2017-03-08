from django.conf import settings
from django.conf.urls import include, url

url_metadata = [
    # django-netjsonconfig schemas
    {
        'regexp': r'^',
        'include': {
            'module': 'django_netjsonconfig.urls',
            'namespace': 'netjsonconfig'
        }
    },
    # openwisp_controller.pki (CRL view)
    {
        'regexp': r'^',
        'app': 'openwisp_controller.pki',
        'include': {
            'module': '{app}.urls',
            'namespace': 'x509'
        }
    },
    # openwisp_controller.config (get_default_templates)
    {
        'regexp': r'^',
        'app': 'openwisp_controller.config',
        'include': {
            'module': '{app}.urls',
            'namespace': 'config'
        }
    },
    # openwisp_controller controller
    {
        'regexp': r'^',
        'app': 'openwisp_controller.config',
        'include': {
            'module': '{app}.controller.urls',
            'namespace': 'controller'
        }
    },
    # owm_legacy
    {
        'regexp': r'^',
        'app': 'owm_legacy',
        'include': {
            'module': '{app}.urls',
            'namespace': 'owm',
        }
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

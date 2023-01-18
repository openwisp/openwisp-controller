from .settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'openwisp2',
        'USER': 'openwisp2',
        'PASSWORD': 'openwisp2',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    },
}

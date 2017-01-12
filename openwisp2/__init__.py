VERSION = (0, 1, 0, 'alpha')
__version__ = VERSION  # alias


def get_version():
    version = '%s.%s.%s' % (VERSION[0], VERSION[1], VERSION[2])
    if VERSION[3] != 'final':
        first_letter = VERSION[3][0:1]
        try:
            suffix = VERSION[4]
        except IndexError:
            suffix = 0
        version = '%s%s%s' % (version, first_letter, suffix)
    return version


default_app_config = 'openwisp2.apps.OpenWisp2App'

# OpenWISP2 extends and depends on these apps which
# cannot be listed in ``settings.INSTALLED_APPS``
# this variable is used by:
#   - openwisp2.staticfiles.DependencyFinder
__dependencies__ = (
    'django_x509',
    'django_netjsonconfig'
)

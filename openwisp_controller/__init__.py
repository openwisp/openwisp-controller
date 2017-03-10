VERSION = (0, 1, 1, 'final')
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


# openwisp-controller extends and depends on these apps which
# cannot be listed in ``settings.INSTALLED_APPS``
# this variable is used by:
#   - openwisp_controller.staticfiles.DependencyFinder
#   - openwisp_controller.loaders.DependencyLoader
__dependencies__ = (
    'django_x509',
    'django_netjsonconfig'
)

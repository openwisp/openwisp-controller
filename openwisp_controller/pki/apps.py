from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django_x509.apps import DjangoX509Config
from swapper import get_model_name

from openwisp_utils.admin_theme.menu import register_menu_group

if not hasattr(settings, 'DJANGO_X509_CA_MODEL'):
    setattr(settings, 'DJANGO_X509_CA_MODEL', 'pki.Ca')
if not hasattr(settings, 'DJANGO_X509_CERT_MODEL'):
    setattr(settings, 'DJANGO_X509_CERT_MODEL', 'pki.Cert')


class PkiConfig(DjangoX509Config):
    name = 'openwisp_controller.pki'
    verbose_name = _('Public Key Infrastructure')

    def ready(self):
        super().ready()
        self.register_menu_groups()

    def register_menu_groups(self):
        register_menu_group(
            position=60,
            config={
                'label': 'Cas & Certificates',
                'items': {
                    1: {
                        'label': 'Certification Authorities',
                        'model': get_model_name('django_x509', 'Ca'),
                        'name': 'changelist',
                        'icon': 'ow-ca',
                    },
                    2: {
                        'label': 'Certificates',
                        'model': get_model_name('django_x509', 'Cert'),
                        'name': 'changelist',
                        'icon': 'ow-certificate',
                    },
                },
                'icon': 'ow-cer-group',
            },
        )

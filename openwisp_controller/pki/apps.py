from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

if not hasattr(settings, 'DJANGO_X509_CA_MODEL'):
    setattr(settings, 'DJANGO_X509_CA_MODEL', 'pki.Ca')
if not hasattr(settings, 'DJANGO_X509_CERT_MODEL'):
    setattr(settings, 'DJANGO_X509_CERT_MODEL', 'pki.Cert')


class PkiConfig(AppConfig):
    name = 'openwisp_controller.pki'
    verbose_name = _('Public Key Infrastructure')

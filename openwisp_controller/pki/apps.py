from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class PkiConfig(AppConfig):
    name = 'openwisp_controller.pki'
    verbose_name = _('Public Key Infrastructure')

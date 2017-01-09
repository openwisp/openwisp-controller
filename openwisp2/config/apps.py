from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class ConfigConfig(AppConfig):
    name = 'openwisp2.config'
    verbose_name = _('Configurations')

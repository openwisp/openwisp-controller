from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _
from django_netjsonconfig.signals import config_modified


class ConnectionConfig(AppConfig):
    name = 'openwisp_controller.connection'
    label = 'connection'
    verbose_name = _('Network Device Credentials')

    def ready(self):
        # connect to config_modified signal
        from .models import DeviceConnection
        config_modified.connect(DeviceConnection.config_modified_receiver)

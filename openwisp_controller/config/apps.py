from django.conf import settings
from django_netjsonconfig import settings as app_settings
from django_netjsonconfig.apps import DjangoNetjsonconfigApp

# ensure Device.hardware_id field is not flagged as unique
# (because it's flagged as unique_together with organization)
app_settings.HARDWARE_ID_OPTIONS['unique'] = False


class ConfigConfig(DjangoNetjsonconfigApp):
    name = 'openwisp_controller.config'
    label = 'config'

    def ready(self, *args, **kwargs):
        super().ready(*args, **kwargs)
        self.add_default_menu_items()

    def __setmodels__(self):
        from .models import Config, VpnClient
        self.config_model = Config
        self.vpnclient_model = VpnClient

    def check_settings(self):
        pass

    def add_default_menu_items(self):
        menu_setting = 'OPENWISP_DEFAULT_ADMIN_MENU_ITEMS'
        items = [
            {'model': 'config.Device'},
            {'model': 'config.Template'},
            {'model': 'config.Vpn'},
        ]
        if not hasattr(settings, menu_setting):
            setattr(settings, menu_setting, items)
        else:
            current_menu = getattr(settings, menu_setting)
            current_menu += items

from django_netjsonconfig.apps import DjangoNetjsonconfigApp


class ConfigConfig(DjangoNetjsonconfigApp):
    name = 'openwisp_controller.config'
    label = 'config'

    def __setmodels__(self):
        from .models import Config, VpnClient
        self.config_model = Config
        self.vpnclient_model = VpnClient

    def check_settings(self):
        pass

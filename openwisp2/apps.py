from django.apps import AppConfig


class OpenWisp2App(AppConfig):
    name = 'openwisp2'
    label = 'OpenWISP'

    def connect_signals(self):
        """
        TODO
        """
        pass

    def check_settings(self):
        pass

    def ready(self):
        pass

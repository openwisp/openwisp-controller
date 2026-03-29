from django.apps import AppConfig


class LeafletConfig(AppConfig):
    name = 'leaflet'
    verbose_name = "Leaflet"

    def ready(self):
        from . import _normalize_plugins_config
        _normalize_plugins_config()

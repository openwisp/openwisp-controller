from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import m2m_changed, post_delete
from django.utils.translation import ugettext_lazy as _

from . import settings as app_settings

# ensure Device.hardware_id field is not flagged as unique
# (because it's flagged as unique_together with organization)
app_settings.HARDWARE_ID_OPTIONS['unique'] = False


class ConfigConfig(AppConfig):
    name = 'openwisp_controller.config'
    label = 'config'
    verbose_name = _('Network Configuration')

    def ready(self, *args, **kwargs):
        self.__setmodels__()
        self.check_settings()
        self.connect_signals()
        self.add_default_menu_items()

    def __setmodels__(self):
        from .models import Config, VpnClient

        self.config_model = Config
        self.vpnclient_model = VpnClient

    def connect_signals(self):
        """
        * m2m validation before templates are added/removed to a config
        * automatic vpn client management on m2m_changed
        * automatic vpn client removal
        """
        m2m_changed.connect(
            self.config_model.clean_templates,
            sender=self.config_model.templates.through,
        )
        m2m_changed.connect(
            self.config_model.templates_changed,
            sender=self.config_model.templates.through,
        )
        m2m_changed.connect(
            self.config_model.manage_vpn_clients,
            sender=self.config_model.templates.through,
        )
        post_delete.connect(
            self.vpnclient_model.post_delete, sender=self.vpnclient_model
        )

    def check_settings(self):
        if (
            settings.DEBUG is False
            and app_settings.REGISTRATION_ENABLED
            and not app_settings.SHARED_SECRET
        ):  # pragma: nocover
            raise ImproperlyConfigured(
                'Security error: NETJSONCONFIG_SHARED_SECRET is not set. '
                'Please set it or disable auto-registration by setting '
                'NETJSONCONFIG_REGISTRATION_ENABLED to False'
            )

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

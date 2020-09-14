from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import m2m_changed, post_delete
from django.utils.translation import ugettext_lazy as _
from openwisp_notifications.types import (
    register_notification_type,
    unregister_notification_type,
)
from swapper import get_model_name, load_model

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
        self.connect_signals()
        self.add_default_menu_items()
        self.register_notification_types()
        self.add_ignore_notification_widget()

    def __setmodels__(self):
        self.config_model = load_model('config', 'Config')
        self.vpnclient_model = load_model('config', 'VpnClient')

    def connect_signals(self):
        """
        * handlers for creating notifications
        * m2m validation before templates are added/removed to a config
        * automatic vpn client management on m2m_changed
        * automatic vpn client removal
        """
        from . import handlers  # noqa

        m2m_changed.connect(
            self.config_model.clean_templates,
            sender=self.config_model.templates.through,
            dispatch_uid='config.clean_templates',
        )
        m2m_changed.connect(
            self.config_model.templates_changed,
            sender=self.config_model.templates.through,
            dispatch_uid='config.templates_changed',
        )
        m2m_changed.connect(
            self.config_model.manage_vpn_clients,
            sender=self.config_model.templates.through,
            dispatch_uid='config.manage_vpn_clients',
        )
        post_delete.connect(
            self.vpnclient_model.post_delete,
            sender=self.vpnclient_model,
            dispatch_uid='vpnclient.post_delete',
        )

    def add_default_menu_items(self):
        menu_setting = 'OPENWISP_DEFAULT_ADMIN_MENU_ITEMS'
        items = [
            {'model': get_model_name('config', 'Device')},
            {'model': get_model_name('config', 'Template')},
            {'model': get_model_name('config', 'Vpn')},
        ]
        if not hasattr(settings, menu_setting):
            setattr(settings, menu_setting, items)
        else:
            current_menu = getattr(settings, menu_setting)
            current_menu += items

    def register_notification_types(self):
        register_notification_type(
            'config_error',
            {
                'verbose_name': _('Configuration ERROR'),
                'verb': _('encountered an error'),
                'level': 'error',
                'email_subject': _(
                    '[{site.name}] ERROR: "{notification.target}" configuration '
                    '{notification.verb}'
                ),
                'message': _(
                    'The configuration of [{notification.target}]'
                    '({notification.target_link}) has {notification.verb}. '
                    'The last working configuration has been restored from a backup '
                    'present on the filesystem of the device.'
                ),
            },
        )

        register_notification_type(
            'device_registered',
            {
                'verbose_name': _('Device Registration'),
                'verb': _('registered successfully'),
                'level': 'success',
                'email_subject': _(
                    '[{site.name}] SUCCESS: "{notification.target}"'
                    ' {notification.verb}'
                ),
                'message': _(
                    '{condition} device [{notification.target}]'
                    '({notification.target_link}) has {notification.verb}.'
                ),
            },
        )

        #  Unregister default notification type
        try:
            unregister_notification_type('default')
        except ImproperlyConfigured:
            pass

    def add_ignore_notification_widget(self):
        """
        Adds ingore notification widget from openwisp-notifications to DeviceAdmin.
        """
        obj_notification_widget = getattr(
            settings, 'OPENWISP_NOTIFICATIONS_IGNORE_ENABLED_ADMIN', []
        )
        device_admin = 'openwisp_controller.config.admin.DeviceAdmin'
        if device_admin not in obj_notification_widget:
            obj_notification_widget.append(device_admin)
            setattr(
                settings,
                'OPENWISP_NOTIFICATIONS_IGNORE_ENABLED_ADMIN',
                obj_notification_widget,
            )

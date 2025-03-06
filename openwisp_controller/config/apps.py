from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Case, Count, When
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)
from django.utils.translation import gettext_lazy as _
from openwisp_notifications.types import (
    register_notification_type,
    unregister_notification_type,
)
from swapper import get_model_name, load_model

from openwisp_utils.admin_theme import register_dashboard_chart
from openwisp_utils.admin_theme.menu import register_menu_group

from . import settings as app_settings
from .signals import (
    config_backend_changed,
    config_deactivated,
    config_deactivating,
    config_modified,
    device_group_changed,
    device_name_changed,
    group_templates_changed,
    vpn_peers_changed,
    vpn_server_modified,
)

# ensure Device.hardware_id field is not flagged as unique
# (because it's flagged as unique_together with organization)
app_settings.HARDWARE_ID_OPTIONS['unique'] = False


class ConfigConfig(AppConfig):
    name = 'openwisp_controller.config'
    label = 'config'
    verbose_name = _('Network Configuration')
    default_auto_field = 'django.db.models.AutoField'

    def ready(self, *args, **kwargs):
        self.__setmodels__()
        self.connect_signals()
        self.register_notification_types()
        self.add_ignore_notification_widget()
        self.enable_cache_invalidation()
        self.register_dashboard_charts()
        self.register_menu_groups()
        self.notification_cache_update()

    def __setmodels__(self):
        self.device_model = load_model('config', 'Device')
        self.template_model = load_model('config', 'Template')
        self.devicegroup_model = load_model('config', 'DeviceGroup')
        self.config_model = load_model('config', 'Config')
        self.vpn_model = load_model('config', 'Vpn')
        self.vpnclient_model = load_model('config', 'VpnClient')
        self.org_limits = load_model('config', 'OrganizationLimits')
        self.cert_model = load_model('django_x509', 'Cert')
        self.org_model = load_model('openwisp_users', 'Organization')

    def connect_signals(self):
        """
        * handlers for creating notifications
        * m2m validation before templates are added/removed to a config
        * enforcement of required templates
        * automatic vpn client management on m2m_changed
        * automatic vpn client removal
        * cache invalidation
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
        # the order of the following connect() call must be maintained
        m2m_changed.connect(
            self.config_model.enforce_required_templates,
            sender=self.config_model.templates.through,
            dispatch_uid='template.enforce_required_template',
        )
        post_save.connect(
            self.vpnclient_model.post_save,
            sender=self.vpnclient_model,
            dispatch_uid='vpnclient.post_save',
        )
        post_delete.connect(
            self.vpnclient_model.post_delete,
            sender=self.vpnclient_model,
            dispatch_uid='vpnclient.post_delete',
        )
        vpn_peers_changed.connect(
            self.vpn_model.update_vpn_server_configuration,
            sender=self.vpn_model,
            dispatch_uid='vpn.update_vpn_server_configuration',
        )
        post_delete.connect(
            self.vpn_model.post_delete,
            sender=self.vpn_model,
            dispatch_uid='vpn.post_delete',
        )
        post_save.connect(
            self.config_model.certificate_updated,
            sender=self.cert_model,
            dispatch_uid='cert_update_invalidate_checksum_cache',
        )
        group_templates_changed.connect(
            handlers.devicegroup_templates_change_handler,
            sender=self.devicegroup_model,
            dispatch_uid='devicegroup_templates_change_handler.changed',
        )
        post_save.connect(
            handlers.devicegroup_templates_change_handler,
            sender=self.config_model,
            dispatch_uid='devicegroup_templates_change_handler.created',
        )
        config_backend_changed.connect(
            handlers.config_backend_change_handler,
            sender=self.config_model,
            dispatch_uid='devicegroup_templates_change_handler.backend_changed',
        )
        pre_save.connect(
            self.template_model.pre_save_handler,
            sender=self.template_model,
            dispatch_uid='template_pre_save_handler',
        )
        pre_save.connect(
            handlers.organization_disabled_handler,
            sender=self.org_model,
            dispatch_uid='organization_disabled_pre_save_clear_device_checksum_cache',
        )
        post_save.connect(
            self.template_model.post_save_handler,
            sender=self.template_model,
            dispatch_uid='template_post_save_handler',
        )
        post_save.connect(
            self.org_limits.post_save_handler,
            sender=self.org_model,
            dispatch_uid='organization_allowed_devices_post_save_handler',
        )

    def register_menu_groups(self):
        register_menu_group(
            position=20,
            config={
                'label': 'Devices',
                'model': get_model_name('config', 'Device'),
                'name': 'changelist',
                'icon': 'ow-device',
            },
        )
        register_menu_group(
            position=30,
            config={
                'label': 'Configurations',
                'items': {
                    1: {
                        'label': 'Templates',
                        'model': get_model_name('config', 'Template'),
                        'name': 'changelist',
                        'icon': 'ow-template',
                    },
                    2: {
                        'label': 'VPN Servers',
                        'model': get_model_name('config', 'Vpn'),
                        'name': 'changelist',
                        'icon': 'ow-vpn',
                    },
                    4: {
                        'label': 'Device Groups',
                        'model': get_model_name('config', 'DeviceGroup'),
                        'name': 'changelist',
                        'icon': 'ow-device-group',
                    },
                },
                'icon': 'ow-config',
            },
        )

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
                'target_link': (
                    'openwisp_controller.config.utils'
                    '.get_config_error_notification_target_url'
                ),
            },
            models=[self.device_model, self.config_model],
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
            models=[self.device_model],
        )

        register_notification_type(
            'api_task_error',
            {
                'verbose_name': _('Background API Task ERROR'),
                'verb': _('encountered an unrecoverable error'),
                'level': 'error',
                'email_subject': _(
                    '[{site.name}] ERROR: "{notification.target}" - '
                    'VPN Server {action} API Task {notification.verb}'
                ),
                'message': _(
                    'Unable to perform {action} operation on the '
                    '[{notification.target}]({notification.target_link}) VPN server '
                    'due to an unrecoverable error (status code: {status_code})'
                ),
                # Disable email notifications by default
                'email_notification': False,
            },
            models=[self.vpn_model],
        )
        register_notification_type(
            'api_task_recovery',
            {
                'verbose_name': _('Background API Task RECOVERY'),
                'verb': _('has been completed successfully'),
                'level': 'info',
                'email_subject': _(
                    '[{site.name}] RECOVERY: "{notification.target}" - '
                    'VPN Server {action} API Task {notification.verb}'
                ),
                'message': _(
                    'The {action} operation on [{notification.target}]'
                    '({notification.target_link}) {notification.verb}'
                ),
                # Disable email notifications by default
                'email_notification': False,
            },
            models=[self.vpn_model],
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

    def enable_cache_invalidation(self):
        """
        Triggers the cache invalidation for the
        device config checksum (view and model method)
        """
        from .controller.views import DeviceChecksumView
        from .handlers import (
            device_cache_invalidation_handler,
            devicegroup_change_handler,
            devicegroup_delete_handler,
            vpn_server_change_handler,
        )

        post_save.connect(
            DeviceChecksumView.invalidate_get_device_cache,
            sender=self.device_model,
            dispatch_uid='invalidate_get_device_cache',
        )
        config_deactivated.connect(
            self.device_model.config_deactivated_clear_management_ip,
            dispatch_uid='config_deactivated_clear_management_ip',
        )
        config_deactivated.connect(
            DeviceChecksumView.invalidate_get_device_cache_on_config_deactivated,
            dispatch_uid='config_deactivated_invalidate_get_device_cache',
        )
        config_deactivating.connect(
            DeviceChecksumView.invalidate_checksum_cache,
            dispatch_uid='config_deactivated_invalidate_get_device_cache',
        )
        config_modified.connect(
            DeviceChecksumView.invalidate_checksum_cache,
            dispatch_uid='invalidate_checksum_cache',
        )
        device_group_changed.connect(
            devicegroup_change_handler,
            sender=self.device_model,
            dispatch_uid='invalidate_devicegroup_cache_on_device_change',
        )
        post_save.connect(
            devicegroup_change_handler,
            sender=self.devicegroup_model,
            dispatch_uid='invalidate_devicegroup_cache_on_devicegroup_change',
        )
        post_save.connect(
            devicegroup_change_handler,
            sender=self.cert_model,
            dispatch_uid='invalidate_devicegroup_cache_on_certificate_change',
        )
        post_delete.connect(
            devicegroup_delete_handler,
            sender=self.devicegroup_model,
            dispatch_uid='invalidate_devicegroup_cache_on_devicegroup_delete',
        )
        post_delete.connect(
            devicegroup_delete_handler,
            sender=self.cert_model,
            dispatch_uid='invalidate_devicegroup_cache_on_certificate_delete',
        )
        pre_delete.connect(
            device_cache_invalidation_handler,
            sender=self.device_model,
            dispatch_uid='device.invalidate_cache',
        )
        vpn_server_modified.connect(
            vpn_server_change_handler,
            sender=self.vpn_model,
            dispatch_uid='vpn.invalidate_checksum_cache',
        )

    def register_dashboard_charts(self):
        register_dashboard_chart(
            position=1,
            config={
                'name': _('Configuration Status'),
                'query_params': {
                    'app_label': 'config',
                    'model': 'device',
                    'group_by': 'config__status',
                },
                'colors': {
                    'applied': '#267126',
                    'modified': '#ffb442',
                    'error': '#a72d1d',
                    'deactivating': '#353c44',
                    'deactivated': '#000',
                },
                'labels': {
                    'applied': _('applied'),
                    'modified': _('modified'),
                    'error': _('error'),
                    'deactivating': _('deactivating'),
                    'deactivated': _('deactivated'),
                },
            },
        )
        register_dashboard_chart(
            position=10,
            config={
                'name': _('Device Models'),
                'query_params': {
                    'app_label': 'config',
                    'model': 'device',
                    'group_by': 'model',
                },
                # since the field can be empty, we need to
                # define a label and a color for the empty case
                'colors': {'': '#353c44'},
                'labels': {'': _('undefined')},
            },
        )
        register_dashboard_chart(
            position=11,
            config={
                'name': _('Firmware version'),
                'query_params': {
                    'app_label': 'config',
                    'model': 'device',
                    'group_by': 'os',
                },
                # since the field can be empty, we need to
                # define a label and a color for the empty case
                'colors': {'': '#353c44'},
                'labels': {'': _('undefined')},
            },
        )
        register_dashboard_chart(
            position=12,
            config={
                'name': _('System type'),
                'query_params': {
                    'app_label': 'config',
                    'model': 'device',
                    'group_by': 'system',
                },
                # since the field can be empty, we need to
                # define a label and a color for the empty case
                'colors': {'': '#353c44'},
                'labels': {'': _('undefined')},
            },
        )
        if app_settings.GROUP_PIE_CHART:
            register_dashboard_chart(
                position=20,
                config={
                    'name': _('Groups'),
                    'query_params': {
                        'app_label': 'config',
                        'model': 'devicegroup',
                        'annotate': {
                            'active_count': Count(
                                Case(
                                    When(
                                        device__isnull=False,
                                        then=1,
                                    )
                                )
                            ),
                            'empty_count': Count(
                                Case(
                                    When(
                                        device__isnull=True,
                                        then=1,
                                    )
                                )
                            ),
                        },
                        'aggregate': {
                            'active': Count(Case(When(active_count__gt=0, then=1))),
                            'empty': Count(Case(When(empty_count__gt=0, then=1))),
                        },
                    },
                    'colors': {
                        'active': '#2277b4',
                        'empty': '#EF7D2D',
                    },
                    'labels': {
                        'active': _('Active groups'),
                        'empty': _('Empty groups'),
                    },
                    'filters': {
                        'key': 'empty',
                        'active': 'false',
                        'empty': 'true',
                    },
                },
            )

    def notification_cache_update(self):
        from openwisp_notifications.handlers import register_notification_cache_update

        register_notification_cache_update(
            self.device_model,
            device_name_changed,
            dispatch_uid='notification_device_cache_invalidation',
        )

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Case, Count, When
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.urls import register_converter
from django.utils.translation import gettext_lazy as _
from openwisp_notifications.types import (
    register_notification_type,
    unregister_notification_type,
)
from swapper import get_model_name, load_model

from openwisp_utils.admin_theme import register_dashboard_chart
from openwisp_utils.admin_theme.menu import register_menu_group

from . import settings as app_settings
from .converters import UUIDAnyConverter
from .signals import (
    config_backend_changed,
    config_deactivated,
    device_group_changed,
    device_name_changed,
    group_templates_changed,
    vpn_peers_changed,
    vpn_server_modified,
)
from .whois.handlers import connect_whois_handlers

# ensure Device.hardware_id field is not flagged as unique
# (because it's flagged as unique_together with organization)
app_settings.HARDWARE_ID_OPTIONS["unique"] = False

# register at import time so the converter is available when URL
# patterns are first parsed; safe to call before ready() runs
register_converter(UUIDAnyConverter, "uuid_any")


class ConfigConfig(AppConfig):
    name = "openwisp_controller.config"
    label = "config"
    verbose_name = _("Network Configuration")
    default_auto_field = "django.db.models.AutoField"

    def ready(self, *args, **kwargs):
        self.__setmodels__()
        self.connect_signals()
        self.register_notification_types()
        self.add_ignore_notification_widget()
        self.connect_related_changes_handlers()
        self.connect_cache_dependencies()
        self.register_dashboard_charts()
        self.register_menu_groups()
        self.notification_cache_update()
        connect_whois_handlers()

    def connect_cache_dependencies(self):
        """
        Wires the declarative cache-invalidation dependencies.

        Models that own a cached value declare their related-change
        dependencies in ``get_cache_dependencies`` (see
        ``CacheInvalidationMixin``).
        Caches that are not owned by a model (controller view caches and device
        group caches) are declared here. Connecting all of them in one place
        replaces the cache-invalidation ``signal.connect()`` calls that were
        previously scattered across the codebase.
        """
        from .base.cache import CacheDependency, _resolve_pk_snapshot
        from .controller.views import DeviceChecksumView
        from .handlers import (
            devicegroup_delete_handler,
            invalidate_devicegroup_cache_change_handler,
            organization_disabled_handler,
        )

        # Model-owned checksum caches (declared on the models themselves).
        self.config_model.register_cache_dependencies()
        self.vpn_model.register_cache_dependencies()

        dependencies = [
            # DeviceChecksumView caches are invalidated when a device is created,
            # updated, deleted or when its config is deactivated.
            CacheDependency(
                source=self.device_model,
                signal="post_save",
                on_create=True,
                target=DeviceChecksumView.invalidate_get_device_cache,
            ),
            # Deferred to commit so a concurrent request cannot repopulate the
            # cache with a device that is about to be (or was just) deleted.
            # ``post_delete`` + ``_resolve_pk_snapshot`` because Django clears
            # ``instance.pk`` on deleted instances before the deferred
            # on_commit callback runs (see ``_resolve_pk_snapshot``).
            CacheDependency(
                source=self.device_model,
                signal="post_delete",
                resolve=_resolve_pk_snapshot,
                target=DeviceChecksumView.invalidate_get_device_cache,
            ),
            CacheDependency(
                signal_obj=config_deactivated,
                name="config_deactivated",
                target=(
                    DeviceChecksumView.invalidate_get_device_cache_on_config_deactivated
                ),
            ),
            # When an organization is disabled, all its devices are deactivated,
            # so we need to invalidate the controller view caches for all objects.
            CacheDependency(
                source=self.org_model,
                signal="pre_save",
                on_commit=False,
                target=organization_disabled_handler,
            ),
            # Invalidate the DeviceGroupCommonName cache when a device's group,
            # a device group, or a certificate changes.
            CacheDependency(
                signal_obj=device_group_changed,
                name="device_group_changed",
                source=self.device_model,
                target=invalidate_devicegroup_cache_change_handler,
            ),
            CacheDependency(
                source=self.devicegroup_model,
                signal="post_save",
                target=invalidate_devicegroup_cache_change_handler,
            ),
            CacheDependency(
                source=self.cert_model,
                signal="post_save",
                target=invalidate_devicegroup_cache_change_handler,
            ),
            # Kept synchronous (on_commit=False) so devicegroup_delete_handler
            # still receives the live instance and can read organization_id
            # before Django clears instance.pk post-delete. The handler
            # itself defers the actual task enqueue via transaction.on_commit().
            CacheDependency(
                source=self.devicegroup_model,
                signal="post_delete",
                on_commit=False,
                target=devicegroup_delete_handler,
            ),
            # Same as above: kept synchronous so the handler can also read
            # common_name before Django clears instance.pk post-delete.
            CacheDependency(
                source=self.cert_model,
                signal="post_delete",
                on_commit=False,
                target=devicegroup_delete_handler,
            ),
        ]
        for dependency in dependencies:
            dependency.connect(
                dispatch_uid=dependency.build_dispatch_uid("cache_invalidation.app")
            )

    def __setmodels__(self):
        self.device_model = load_model("config", "Device")
        self.template_model = load_model("config", "Template")
        self.devicegroup_model = load_model("config", "DeviceGroup")
        self.config_model = load_model("config", "Config")
        self.vpn_model = load_model("config", "Vpn")
        self.vpnclient_model = load_model("config", "VpnClient")
        self.org_limits = load_model("config", "OrganizationLimits")
        self.cert_model = load_model("django_x509", "Cert")
        self.org_model = load_model("openwisp_users", "Organization")

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
            dispatch_uid="config.clean_templates",
        )
        # VPN clients must be created or removed **before**
        # self.config_model.templates_changed is evaluated, because
        # the VpnClient context can influence the configuration checksum.
        m2m_changed.connect(
            self.config_model.manage_vpn_clients,
            sender=self.config_model.templates.through,
            dispatch_uid="config.manage_vpn_clients",
        )
        m2m_changed.connect(
            self.config_model.templates_changed,
            sender=self.config_model.templates.through,
            dispatch_uid="config.templates_changed",
        )
        # the order of the following connect() call must be maintained
        m2m_changed.connect(
            self.config_model.enforce_required_templates,
            sender=self.config_model.templates.through,
            dispatch_uid="template.enforce_required_template",
        )
        post_save.connect(
            self.vpnclient_model.post_save,
            sender=self.vpnclient_model,
            dispatch_uid="vpnclient.post_save",
        )
        post_delete.connect(
            self.vpnclient_model.post_delete,
            sender=self.vpnclient_model,
            dispatch_uid="vpnclient.post_delete",
        )
        vpn_peers_changed.connect(
            self.vpn_model.update_vpn_server_configuration,
            sender=self.vpn_model,
            dispatch_uid="vpn.update_vpn_server_configuration",
        )
        post_delete.connect(
            self.vpn_model.post_delete,
            sender=self.vpn_model,
            dispatch_uid="vpn.post_delete",
        )
        group_templates_changed.connect(
            handlers.devicegroup_templates_change_handler,
            sender=self.devicegroup_model,
            dispatch_uid="devicegroup_templates_change_handler.changed",
        )
        post_save.connect(
            handlers.devicegroup_templates_change_handler,
            sender=self.config_model,
            dispatch_uid="devicegroup_templates_change_handler.created",
        )
        config_backend_changed.connect(
            handlers.config_backend_change_handler,
            sender=self.config_model,
            dispatch_uid="devicegroup_templates_change_handler.backend_changed",
        )
        pre_save.connect(
            self.template_model.pre_save_handler,
            sender=self.template_model,
            dispatch_uid="template_pre_save_handler",
        )
        post_save.connect(
            self.template_model.post_save_handler,
            sender=self.template_model,
            dispatch_uid="template_post_save_handler",
        )
        post_save.connect(
            self.org_limits.post_save_handler,
            sender=self.org_model,
            dispatch_uid="organization_allowed_devices_post_save_handler",
        )

    def register_menu_groups(self):
        register_menu_group(
            position=20,
            config={
                "label": "Devices",
                "model": get_model_name("config", "Device"),
                "name": "changelist",
                "icon": "ow-device",
            },
        )
        register_menu_group(
            position=30,
            config={
                "label": "Configurations",
                "items": {
                    1: {
                        "label": "Templates",
                        "model": get_model_name("config", "Template"),
                        "name": "changelist",
                        "icon": "ow-template",
                    },
                    2: {
                        "label": "VPN Servers",
                        "model": get_model_name("config", "Vpn"),
                        "name": "changelist",
                        "icon": "ow-vpn",
                    },
                    4: {
                        "label": "Device Groups",
                        "model": get_model_name("config", "DeviceGroup"),
                        "name": "changelist",
                        "icon": "ow-device-group",
                    },
                },
                "icon": "ow-config",
            },
        )

    def register_notification_types(self):
        register_notification_type(
            "config_error",
            {
                "verbose_name": _("Configuration ERROR"),
                "verb": _("encountered an error"),
                "level": "error",
                "email_subject": _(
                    '[{site.name}] ERROR: "{notification.target}" configuration '
                    "{notification.verb}"
                ),
                "message": _(
                    "The configuration of [{notification.target}]"
                    "({notification.target_link}) has {notification.verb}. "
                    "The last working configuration has been restored from a backup "
                    "present on the filesystem of the device."
                ),
                "target_link": (
                    "openwisp_controller.config.utils"
                    ".get_config_error_notification_target_url"
                ),
            },
            models=[self.device_model, self.config_model],
        )

        register_notification_type(
            "device_registered",
            {
                "verbose_name": _("Device Registration"),
                "verb": _("registered successfully"),
                "level": "success",
                "email_subject": _(
                    '[{site.name}] SUCCESS: "{notification.target}"'
                    " {notification.verb}"
                ),
                "message": _(
                    "{condition} device [{notification.target}]"
                    "({notification.target_link}) has {notification.verb}."
                ),
            },
            models=[self.device_model],
        )
        #  Unregister default notification type
        try:
            unregister_notification_type("default")
        except ImproperlyConfigured:
            pass

    def add_ignore_notification_widget(self):
        """
        Adds ingore notification widget from openwisp-notifications to DeviceAdmin.
        """
        obj_notification_widget = getattr(
            settings, "OPENWISP_NOTIFICATIONS_IGNORE_ENABLED_ADMIN", []
        )
        device_admin = "openwisp_controller.config.admin.DeviceAdmin"
        if device_admin not in obj_notification_widget:
            obj_notification_widget.append(device_admin)
            setattr(
                settings,
                "OPENWISP_NOTIFICATIONS_IGNORE_ENABLED_ADMIN",
                obj_notification_widget,
            )

    def connect_related_changes_handlers(self):
        """
        Connects signal handlers that react to a change in one object by
        propagating side effects to related objects. These are intentionally
        kept out of the declarative cache-invalidation engine (see
        ``connect_cache_dependencies``) because they do more than invalidate a
        cached value:

        * clearing a device's management IP when its config is deactivated;
        * re-applying group templates when a device's group changes
          (``devicegroup_change_handler``);
        * refreshing the configs of a VPN server's clients when the server
          changes. ``vpn_server_change_handler`` recomputes each client's
          checksum and emits ``config_modified`` for it, but only when that
          checksum actually changed.
        """
        from .handlers import devicegroup_change_handler, vpn_server_change_handler

        config_deactivated.connect(
            self.device_model.config_deactivated_clear_management_ip,
            dispatch_uid="config_deactivated_clear_management_ip",
        )
        device_group_changed.connect(
            devicegroup_change_handler,
            sender=self.device_model,
            dispatch_uid="manage_devicegroup_templates_on_device_change",
        )
        vpn_server_modified.connect(
            vpn_server_change_handler,
            sender=self.vpn_model,
            dispatch_uid="vpn.invalidate_checksum_cache",
        )

    def register_dashboard_charts(self):
        register_dashboard_chart(
            position=1,
            config={
                "name": _("Configuration Status"),
                "query_params": {
                    "app_label": "config",
                    "model": "device",
                    "group_by": "config__status",
                },
                "colors": {
                    "applied": "#267126",
                    "modified": "#ffb442",
                    "error": "#a72d1d",
                    "deactivating": "#353c44",
                    "deactivated": "#000",
                },
                "labels": {
                    "applied": _("applied"),
                    "modified": _("modified"),
                    "error": _("error"),
                    "deactivating": _("deactivating"),
                    "deactivated": _("deactivated"),
                },
            },
        )
        register_dashboard_chart(
            position=10,
            config={
                "name": _("Device Models"),
                "query_params": {
                    "app_label": "config",
                    "model": "device",
                    "group_by": "model",
                },
                # since the field can be empty, we need to
                # define a label and a color for the empty case
                "colors": {"": "#353c44"},
                "labels": {"": _("undefined")},
            },
        )
        register_dashboard_chart(
            position=11,
            config={
                "name": _("Firmware version"),
                "query_params": {
                    "app_label": "config",
                    "model": "device",
                    "group_by": "os",
                },
                # since the field can be empty, we need to
                # define a label and a color for the empty case
                "colors": {"": "#353c44"},
                "labels": {"": _("undefined")},
            },
        )
        register_dashboard_chart(
            position=12,
            config={
                "name": _("System type"),
                "query_params": {
                    "app_label": "config",
                    "model": "device",
                    "group_by": "system",
                },
                # since the field can be empty, we need to
                # define a label and a color for the empty case
                "colors": {"": "#353c44"},
                "labels": {"": _("undefined")},
            },
        )
        if app_settings.GROUP_PIE_CHART:
            register_dashboard_chart(
                position=20,
                config={
                    "name": _("Groups"),
                    "query_params": {
                        "app_label": "config",
                        "model": "devicegroup",
                        "annotate": {
                            "active_count": Count(
                                Case(
                                    When(
                                        device__isnull=False,
                                        then=1,
                                    )
                                )
                            ),
                            "empty_count": Count(
                                Case(
                                    When(
                                        device__isnull=True,
                                        then=1,
                                    )
                                )
                            ),
                        },
                        "aggregate": {
                            "active": Count(Case(When(active_count__gt=0, then=1))),
                            "empty": Count(Case(When(empty_count__gt=0, then=1))),
                        },
                    },
                    "colors": {
                        "active": "#2277b4",
                        "empty": "#EF7D2D",
                    },
                    "labels": {
                        "active": _("Active groups"),
                        "empty": _("Empty groups"),
                    },
                    "filters": {
                        "key": "empty",
                        "active": "false",
                        "empty": "true",
                    },
                },
            )

    def notification_cache_update(self):
        from openwisp_notifications.handlers import register_notification_cache_update

        register_notification_cache_update(
            self.device_model,
            device_name_changed,
            dispatch_uid="notification_device_cache_invalidation",
        )

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from openwisp_notifications.swapper import load_model
from openwisp_notifications.widgets import _add_object_notification_widget
from openwisp_users.admin import OrganizationAdmin

OrganizationNotificationSettings = load_model("OrganizationNotificationSettings")


class OrganizationNotificationSettingsInline(admin.StackedInline):
    model = OrganizationNotificationSettings
    extra = 0
    can_delete = False
    verbose_name = _("Notification Settings")
    verbose_name_plural = _("Notification Settings")

    class Media:
        js = [
            "admin/js/jquery.init.js",
            "openwisp-notifications/js/organization-settings.js",
        ]


OrganizationAdmin.inlines.insert(2, OrganizationNotificationSettingsInline)
_add_object_notification_widget()

from django import forms
from django.contrib import admin

from . import settings as app_settings
from .base.admin import (
    AbstractConfigForm,
    AbstractConfigInline,
    AbstractDeviceAdmin,
    AbstractTemplateAdmin,
    AbstractVpnAdmin,
    AbstractVpnForm,
    BaseForm,
)
from .models import Config, Device, OrganizationConfigSettings, Template, Vpn


class ConfigForm(AbstractConfigForm):
    class Meta(AbstractConfigForm.Meta):
        model = Config


class ConfigInline(AbstractConfigInline):
    model = Config
    form = ConfigForm


class DeviceAdmin(AbstractDeviceAdmin):
    inlines = [ConfigInline]


class TemplateForm(BaseForm):
    class Meta(BaseForm.Meta):
        model = Template


class TemplateAdmin(AbstractTemplateAdmin):
    form = TemplateForm


class VpnForm(AbstractVpnForm):
    class Meta(AbstractVpnForm.Meta):
        model = Vpn


class VpnAdmin(AbstractVpnAdmin):
    form = VpnForm


admin.site.register(Device, DeviceAdmin)
admin.site.register(Template, TemplateAdmin)
admin.site.register(Vpn, VpnAdmin)


if getattr(app_settings, 'REGISTRATION_ENABLED', True):
    from openwisp_utils.admin import AlwaysHasChangedMixin
    from openwisp_users.admin import OrganizationAdmin

    class ConfigSettingsForm(AlwaysHasChangedMixin, forms.ModelForm):
        pass

    class ConfigSettingsInline(admin.StackedInline):
        model = OrganizationConfigSettings
        form = ConfigSettingsForm

    OrganizationAdmin.save_on_top = True
    OrganizationAdmin.inlines.insert(0, ConfigSettingsInline)

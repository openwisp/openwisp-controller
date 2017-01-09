from django.contrib import admin

from django_netjsonconfig.base.admin import (AbstractConfigAdmin,
                                             AbstractConfigForm,
                                             AbstractTemplateAdmin,
                                             AbstractVpnAdmin, AbstractVpnForm,
                                             BaseForm)

from .models import Config, Template, Vpn


class ConfigForm(AbstractConfigForm):
    class Meta(AbstractConfigForm.Meta):
        model = Config


class ConfigAdmin(AbstractConfigAdmin):
    form = ConfigForm


ConfigAdmin.list_display.insert(1, 'organization')
ConfigAdmin.list_filter.insert(0, 'organization')
ConfigAdmin.fields.insert(1, 'organization')


class TemplateForm(BaseForm):
    class Meta(BaseForm.Meta):
        model = Template


class TemplateAdmin(AbstractTemplateAdmin):
    form = TemplateForm


TemplateAdmin.list_display.insert(1, 'organization')
TemplateAdmin.list_filter.insert(0, 'organization')
TemplateAdmin.fields.insert(1, 'organization')


class VpnForm(AbstractVpnForm):
    class Meta(AbstractVpnForm.Meta):
        model = Vpn


class VpnAdmin(AbstractVpnAdmin):
    form = VpnForm


VpnAdmin.list_display.insert(1, 'organization')
VpnAdmin.list_filter.insert(0, 'organization')
VpnAdmin.fields.insert(2, 'organization')


admin.site.register(Config, ConfigAdmin)
admin.site.register(Template, TemplateAdmin)
admin.site.register(Vpn, VpnAdmin)

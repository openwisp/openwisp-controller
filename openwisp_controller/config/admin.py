import json

from django import forms
from django.contrib import admin
from django.urls import reverse
from django_netjsonconfig import settings as django_netjsonconfig_settings
from django_netjsonconfig.base.admin import (AbstractConfigForm, AbstractConfigInline, AbstractDeviceAdmin,
                                             AbstractTemplateAdmin, AbstractVpnAdmin, AbstractVpnForm,
                                             BaseForm)

from openwisp_users.admin import OrganizationAdmin as BaseOrganizationAdmin
from openwisp_users.models import Organization
from openwisp_utils.admin import MultitenantOrgFilter, MultitenantRelatedOrgFilter

from ..admin import AlwaysHasChangedMixin, MultitenantAdminMixin
from .models import Config, Device, OrganizationConfigSettings, Template, Vpn


class ConfigForm(AlwaysHasChangedMixin, AbstractConfigForm):
    class Meta(AbstractConfigForm.Meta):
        model = Config

    def clean_templates(self):
        org = Organization.objects.get(pk=self.data['organization'])
        self.cleaned_data['organization'] = org
        return super(ConfigForm, self).clean_templates()


class ConfigInline(MultitenantAdminMixin, AbstractConfigInline):
    model = Config
    form = ConfigForm
    extra = 0
    multitenant_shared_relations = ('templates',)


class DeviceAdmin(MultitenantAdminMixin, AbstractDeviceAdmin):
    inlines = [ConfigInline]
    list_filter = [('organization', MultitenantOrgFilter),
                   'config__backend',
                   ('config__templates', MultitenantRelatedOrgFilter),
                   'config__status',
                   'created']
    list_select_related = ('config', 'organization')

    def _get_default_template_urls(self):
        """
        returns URLs to get default templates
        used in change_form.html template
        """
        organizations = Organization.active.all()
        urls = {}
        for org in organizations:
            urls[str(org.pk)] = reverse('config:get_default_templates', args=[org.pk])
        return json.dumps(urls)

    def get_extra_context(self, pk=None):
        ctx = super(DeviceAdmin, self).get_extra_context(pk)
        ctx.update({'default_template_urls': self._get_default_template_urls()})
        return ctx

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = self.get_extra_context()
        return super(DeviceAdmin, self).add_view(request, form_url, extra_context)


DeviceAdmin.list_display.insert(1, 'organization')
DeviceAdmin.fields.insert(1, 'organization')


class TemplateForm(BaseForm):
    class Meta(BaseForm.Meta):
        model = Template


class TemplateAdmin(MultitenantAdminMixin, AbstractTemplateAdmin):
    form = TemplateForm
    multitenant_shared_relations = ('vpn',)


TemplateAdmin.list_display.insert(1, 'organization')
TemplateAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))
TemplateAdmin.fields.insert(1, 'organization')


class VpnForm(AbstractVpnForm):
    class Meta(AbstractVpnForm.Meta):
        model = Vpn


class VpnAdmin(MultitenantAdminMixin, AbstractVpnAdmin):
    form = VpnForm
    multitenant_shared_relations = ('ca', 'cert')


VpnAdmin.list_display.insert(1, 'organization')
VpnAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))
VpnAdmin.list_filter.remove('ca')
VpnAdmin.fields.insert(2, 'organization')


class ConfigSettingsForm(AlwaysHasChangedMixin, forms.ModelForm):
    pass


class ConfigSettingsInline(admin.StackedInline):
    model = OrganizationConfigSettings
    form = ConfigSettingsForm


class OrganizationAdmin(BaseOrganizationAdmin):
    save_on_top = True
    inlines = [ConfigSettingsInline] + BaseOrganizationAdmin.inlines


admin.site.register(Device, DeviceAdmin)
admin.site.register(Template, TemplateAdmin)
admin.site.register(Vpn, VpnAdmin)


if getattr(django_netjsonconfig_settings, 'REGISTRATION_ENABLED', True):
    # add OrganizationConfigSettings inline to Organization admin
    admin.site.unregister(Organization)
    admin.site.register(Organization, OrganizationAdmin)

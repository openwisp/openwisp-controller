import json

from django import forms
from django.contrib import admin
from django.urls import reverse

from django_netjsonconfig import settings as django_netjsonconfig_settings
from django_netjsonconfig.base.admin import (AbstractConfigAdmin,
                                             AbstractConfigForm,
                                             AbstractTemplateAdmin,
                                             AbstractVpnAdmin, AbstractVpnForm,
                                             BaseConfigAdmin, BaseForm)
from openwisp_controller.admin import MultitenantAdminMixin, MultitenantOrgFilter
from openwisp_users.admin import OrganizationAdmin as BaseOrganizationAdmin
from openwisp_users.models import Organization

from .models import Config, OrganizationConfigSettings, Template, Vpn


class ConfigForm(AbstractConfigForm):
    class Meta(AbstractConfigForm.Meta):
        model = Config


class ConfigAdmin(MultitenantAdminMixin, AbstractConfigAdmin):
    form = ConfigForm
    model = Config
    multitenant_shared_relations = ('templates',)

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
        ctx = super(ConfigAdmin, self).get_extra_context(pk)
        ctx.update({'default_template_urls': self._get_default_template_urls()})
        return ctx

    def add_view(self, request, form_url='', extra_context={}):
        extra_context.update(self.get_extra_context())
        return super(BaseConfigAdmin, self).add_view(request, form_url, extra_context)


ConfigAdmin.list_display.insert(1, 'organization')
ConfigAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))
ConfigAdmin.fields.insert(1, 'organization')


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


class ConfigSettingsForm(forms.ModelForm):
    def has_changed(self):
        """
        This django-admin trick ensures the settings
        are saved even if default values are unchanged
        (without this trick new setting objects won't be
        created unless users change the default values)
        """
        if self.instance._state.adding:
            return True
        return super(ConfigSettingsForm, self).has_changed()


class ConfigSettingsInline(admin.StackedInline):
    model = OrganizationConfigSettings
    form = ConfigSettingsForm


class OrganizationAdmin(BaseOrganizationAdmin):
    save_on_top = True
    inlines = [ConfigSettingsInline] + BaseOrganizationAdmin.inlines


admin.site.register(Config, ConfigAdmin)
admin.site.register(Template, TemplateAdmin)
admin.site.register(Vpn, VpnAdmin)


if getattr(django_netjsonconfig_settings, 'REGISTRATION_ENABLED', True):
    # add OrganizationConfigSettings inline to Organization admin
    admin.site.unregister(Organization)
    admin.site.register(Organization, OrganizationAdmin)

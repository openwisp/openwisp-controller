import json

from django import forms
from django.contrib import admin
from django.db.models import Q
from django.urls import reverse

from django_netjsonconfig import settings as django_netjsonconfig_settings
from django_netjsonconfig.base.admin import (AbstractConfigAdmin,
                                             AbstractConfigForm,
                                             AbstractTemplateAdmin,
                                             AbstractVpnAdmin, AbstractVpnForm,
                                             BaseConfigAdmin, BaseForm)
from openwisp2.users.admin import OrganizationAdmin as BaseOrganizationAdmin
from openwisp2.users.models import Organization, OrganizationUser

from .models import Config, OrganizationConfigSettings, Template, Vpn


class ConfigForm(AbstractConfigForm):
    class Meta(AbstractConfigForm.Meta):
        model = Config


class ConfigAdmin(AbstractConfigAdmin):
    form = ConfigForm
    model = Config
    select_default_templates = False

    def get_organizations_for_user(self, user):
        return OrganizationUser.objects.filter(user=user).only('organization').values_list('organization')

    def get_queryset(self, request):
        """
        if current user is not superuser, show only the
        configurations of relevant organizations
        """
        qs = super(ConfigAdmin, self).get_queryset(request)
        if request.user.is_superuser:
            return qs
        organizations = self.get_organizations_for_user(request.user)
        return qs.filter(organization__in=organizations)

    def get_form(self, request, obj=None, **kwargs):
        """
        if current user is not superuser:
            * show only relevant organizations
            * show only templates of relevant organizations
              and shared templates
        """
        form = super(ConfigAdmin, self).get_form(request, obj, **kwargs)
        if request.user.is_superuser is False:
            organizations = self.get_organizations_for_user(request.user)
            # organizations
            field = form.base_fields['organization']
            field.queryset = field.queryset.filter(pk__in=organizations)
            # templates
            field = form.base_fields['templates']
            field.queryset = field.queryset.filter(Q(organization__in=organizations) | Q(organization=None))
        return form

    def _get_default_template_urls(self):
        """
        returns URLs to get default templates
        used in change_form.html template
        """
        organizations = self.model.organization.get_queryset()
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

import json

from django import forms
from django.conf.urls import url
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django_netjsonconfig import settings as app_settings
from django_netjsonconfig.base.admin import (AbstractConfigForm, AbstractConfigInline, AbstractDeviceAdmin,
                                             AbstractTemplateAdmin, AbstractVpnAdmin, AbstractVpnForm,
                                             BaseForm)
from openwisp_controller.config.views import get_default_templates

from openwisp_users.models import Organization
from openwisp_users.multitenancy import MultitenantOrgFilter, MultitenantRelatedOrgFilter
from openwisp_utils.admin import AlwaysHasChangedMixin

from ..admin import MultitenantAdminMixin
from .forms import CloneOrganizationForm
from .models import Config, Device, OrganizationConfigSettings, Template, Vpn


class ConfigForm(AlwaysHasChangedMixin, AbstractConfigForm):
    class Meta(AbstractConfigForm.Meta):
        model = Config

    def get_temp_model_instance(self, **options):
        config_model = self.Meta.model
        instance = config_model(**options)
        device_model = config_model.device.field.related_model
        org = Organization.objects.get(pk=self.data['organization'])
        instance.device = device_model(
            name=self.data['name'],
            mac_address=self.data['mac_address'],
            organization=org
        )
        return instance


class ConfigInline(MultitenantAdminMixin, AbstractConfigInline):
    model = Config
    form = ConfigForm
    extra = 0
    multitenant_shared_relations = ('templates',)


class DeviceAdmin(MultitenantAdminMixin, AbstractDeviceAdmin):
    inlines = [ConfigInline]
    list_filter = [('organization', MultitenantOrgFilter),
                   ('config__templates', MultitenantRelatedOrgFilter),
                   'config__status',
                   'created']
    if app_settings.BACKEND_DEVICE_LIST:
        list_filter.insert(1, 'config__backend')
    list_select_related = ('config', 'organization')

    def _get_default_template_urls(self):
        """
        returns URLs to get default templates
        used in change_form.html template
        """
        organizations = Organization.active.all()
        urls = {}
        for org in organizations:
            urls[str(org.pk)] = reverse('admin:get_default_templates', args=[org.pk])
        return json.dumps(urls)

    def get_urls(self):
        return [
            url(r'^config/get-default-templates/(?P<organization_id>[^/]+)/$',
                get_default_templates,
                name='get_default_templates'),
        ] + super().get_urls()

    def get_extra_context(self, pk=None):
        ctx = super().get_extra_context(pk)
        ctx.update({'default_template_urls': self._get_default_template_urls()})
        return ctx

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = self.get_extra_context()
        return super().add_view(request, form_url, extra_context)


org_position = 1 if not app_settings.HARDWARE_ID_ENABLED else 2
DeviceAdmin.list_display.insert(org_position, 'organization')
DeviceAdmin.fields.insert(1, 'organization')


class TemplateForm(BaseForm):
    class Meta(BaseForm.Meta):
        model = Template


def clone_selected_templates(modeladmin, request, queryset):
    selectable_orgs = None
    if request.user.is_superuser:
        all_orgs = Organization.objects.all()
        if all_orgs.count() > 1:
            selectable_orgs = all_orgs
    elif len(request.user.organizations_pk) > 1:
        selectable_orgs = Organization.objects.filter(pk__in=request.user.organizations_pk)
    if selectable_orgs:
        if request.POST.get('organization'):
            for template in queryset:
                clone = template.clone(request.user)
                clone.organization = Organization.objects.get(pk=request.POST.get('organization'))
                clone.save()
            modeladmin.message_user(request, _('Successfully cloned selected templates.'), messages.SUCCESS)
            return None

        context = {
            'title': _('Clone templates'),
            'queryset': queryset,
            'opts': modeladmin.model._meta,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'form': CloneOrganizationForm(queryset=selectable_orgs)
        }
        return TemplateResponse(request, 'admin/config/clone_template_form.html', context)
    else:
        for template in queryset:
            clone = template.clone(request.user)
            clone.save()


class TemplateAdmin(MultitenantAdminMixin, AbstractTemplateAdmin):
    form = TemplateForm
    multitenant_shared_relations = ('vpn',)
    actions = [clone_selected_templates]


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

admin.site.register(Device, DeviceAdmin)
admin.site.register(Template, TemplateAdmin)
admin.site.register(Vpn, VpnAdmin)


if getattr(app_settings, 'REGISTRATION_ENABLED', True):
    from openwisp_users.admin import OrganizationAdmin

    class ConfigSettingsForm(AlwaysHasChangedMixin, forms.ModelForm):
        pass

    class ConfigSettingsInline(admin.StackedInline):
        model = OrganizationConfigSettings
        form = ConfigSettingsForm

    OrganizationAdmin.save_on_top = True
    OrganizationAdmin.inlines.insert(0, ConfigSettingsInline)

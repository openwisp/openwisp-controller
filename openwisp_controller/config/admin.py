import json
import logging

import reversion
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import (
    FieldDoesNotExist,
    ObjectDoesNotExist,
    ValidationError,
)
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.template.response import TemplateResponse
from django.urls import path, re_path, reverse
from django.utils.translation import gettext_lazy as _
from flat_json_widget.widgets import FlatJsonWidget
from swapper import load_model

from openwisp_controller.config.views import (
    get_relevant_templates,
    get_template_default_values,
)
from openwisp_users.multitenancy import (
    MultitenantOrgFilter,
    MultitenantRelatedOrgFilter,
)
from openwisp_utils.admin import (
    AlwaysHasChangedMixin,
    TimeReadonlyAdminMixin,
    UUIDAdmin,
)

from ..admin import MultitenantAdminMixin
from . import settings as app_settings
from .base.vpn import AbstractVpn
from .utils import send_file
from .widgets import DeviceGroupJsonSchemaWidget, JsonSchemaWidget

logger = logging.getLogger(__name__)
prefix = 'config/'
Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
DeviceGroup = load_model('config', 'DeviceGroup')
Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Organization = load_model('openwisp_users', 'Organization')
OrganizationConfigSettings = load_model('config', 'OrganizationConfigSettings')

if 'reversion' in settings.INSTALLED_APPS:
    from reversion.admin import VersionAdmin as ModelAdmin
else:  # pragma: nocover
    from django.contrib.admin import ModelAdmin


class SystemDefinedVariableMixin(object):
    def system_context(self, obj):
        system_context = obj.get_system_context()
        template = get_template('admin/config/system_context.html')
        output = template.render({'system_context': system_context, 'new_line': '\n'})
        return output

    system_context.short_description = _('System Defined Variables')


class BaseAdmin(TimeReadonlyAdminMixin, ModelAdmin):
    history_latest_first = True


class BaseConfigAdmin(BaseAdmin):
    change_form_template = 'admin/config/change_form.html'
    preview_template = None
    actions_on_bottom = True
    save_on_top = True
    ordering = ['name']

    class Media:
        css = {'all': (f'{prefix}css/admin.css',)}
        js = list(UUIDAdmin.Media.js) + [
            f'{prefix}js/{file_}'
            for file_ in ('preview.js', 'unsaved_changes.js', 'switcher.js')
        ]

    def get_extra_context(self, pk=None):
        prefix = 'admin:{0}_{1}'.format(
            self.opts.app_label, self.model.__name__.lower()
        )
        text = _('Preview configuration')
        ctx = {
            'additional_buttons': [
                {
                    'type': 'button',
                    'url': reverse('{0}_preview'.format(prefix)),
                    'class': 'previewlink',
                    'value': text,
                    'title': '{0} (ALT+P)'.format(text),
                }
            ]
        }
        # do not pass CONFIG_BACKEND_FIELD_SHOWN in VpnAdmin
        # since we don't need to hide the VPN backend there
        if not issubclass(self.model, AbstractVpn):
            ctx['CONFIG_BACKEND_FIELD_SHOWN'] = app_settings.CONFIG_BACKEND_FIELD_SHOWN
        if pk:
            ctx['download_url'] = reverse('{0}_download'.format(prefix), args=[pk])
            try:
                has_config = True
                if self.model.__name__ == 'Device':
                    has_config = self.model.objects.get(pk=pk)._has_config()
            except (ObjectDoesNotExist, ValidationError):
                raise Http404()
            else:
                if not has_config:
                    ctx['download_url'] = None
        return ctx

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context.update(self.get_extra_context())
        instance = self.model()
        if hasattr(instance, 'get_default_templates'):
            templates = instance.get_default_templates()
            templates = [str(t.id) for t in templates]
            extra_context.update({'default_templates': templates})
        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = self.get_extra_context(object_id)
        return super().change_view(request, object_id, form_url, extra_context)

    def get_urls(self):
        options = getattr(self.model, '_meta')
        url_prefix = '{0}_{1}'.format(options.app_label, options.model_name)
        return [
            re_path(
                r'^download/(?P<pk>[^/]+)/$',
                self.admin_site.admin_view(self.download_view),
                name='{0}_download'.format(url_prefix),
            ),
            path(
                'preview/',
                self.admin_site.admin_view(self.preview_view),
                name='{0}_preview'.format(url_prefix),
            ),
            re_path(
                r'^(?P<pk>[^/]+)/context\.json$',
                self.admin_site.admin_view(self.context_view),
                name='{0}_context'.format(url_prefix),
            ),
        ] + super().get_urls()

    def _get_config_model(self):
        model = self.model
        if hasattr(model, 'get_backend_instance'):
            return model
        return model.get_config_model()

    def _get_preview_instance(self, request):
        """
        returns a temporary instance used for preview
        """
        kwargs = {}
        config_model = self._get_config_model()
        instance = config_model()
        for key, value in request.POST.items():
            # skip keys that are not model fields
            try:
                field = config_model._meta.get_field(key)
            except FieldDoesNotExist:
                continue
            # skip m2m
            if field.many_to_many:
                continue
            # skip if falsy value and PK or relations
            elif not value and any([field.primary_key, field.is_relation]):
                continue
            # adapt attribute names to the fact that we only
            # have pk of relations, therefore use {relation}_id
            elif field.is_relation:
                key = '{relation}_id'.format(relation=key)
                # pass non-empty string or None
                kwargs[key] = value or None
            # put regular field values in kwargs dict
            else:
                kwargs[key] = value
        # default context to None to avoid exception
        if 'context' in kwargs:
            kwargs['context'] = kwargs['context'] or None
        try:
            instance = config_model.objects.get(pk=request.POST['id'])
            for key, value in kwargs.items():
                setattr(instance, key, value)
        except (KeyError, ValidationError, config_model.DoesNotExist):
            # this object is instanciated only to generate the preview
            # it won't be saved to the database
            instance = config_model(**kwargs)
        # turn off special name validation
        # (see ``ShareableOrgMixinUniqueName``)
        instance._validate_name = False
        instance.full_clean(exclude=['device'], validate_unique=False)
        return instance

    preview_error_msg = _('Preview for {0} with name {1} failed')

    def preview_view(self, request):
        if request.method != 'POST':
            msg = _('Preview: request method {0} is not allowed').format(request.method)
            logger.warning(msg, extra={'request': request, 'stack': True})
            return HttpResponse(status=405)
        config_model = self._get_config_model()
        error = None
        output = None
        # error message for eventual exceptions
        error_msg = self.preview_error_msg.format(
            config_model.__name__, request.POST.get('name')
        )
        try:
            instance = self._get_preview_instance(request)
        except Exception as e:
            logger.exception(error_msg, extra={'request': request})
            # return 400 for validation errors, otherwise 500
            status = 400 if e.__class__ is ValidationError else 500
            return HttpResponse(str(e), status=status)
        template_ids = request.POST.get('templates')
        if template_ids:
            template_model = config_model.get_template_model()
            template_ids = template_ids.split(',')
            try:
                templates = template_model.objects.filter(pk__in=template_ids)
                templates = list(templates)  # evaluating queryset performs query
                # ensure the order of templates is maintained
                templates.sort(
                    key=lambda template: template_ids.index(str(template.id))
                )
            except ValidationError as e:
                logger.exception(error_msg, extra={'request': request})
                return HttpResponse(str(e), status=400)
        else:
            templates = None
        if not error:
            context = instance.get_context()
            backend = instance.get_backend_instance(
                template_instances=templates, context=context
            )
            try:
                instance.clean_netjsonconfig_backend(backend)
                output = backend.render()
            except ValidationError as e:
                error = str(e)
        context = self.admin_site.each_context(request)
        opts = self.model._meta
        context.update(
            {
                'is_popup': True,
                'opts': opts,
                'change': False,
                'output': output,
                'media': self.media,
                'error': error,
            }
        )
        return TemplateResponse(
            request,
            self.preview_template
            or [
                'admin/config/%s/preview.html' % (opts.model_name),
                'admin/config/preview.html',
            ],
            context,
        )

    def download_view(self, request, pk):
        instance = get_object_or_404(self.model, pk=pk)
        if hasattr(instance, 'generate'):
            config = instance
        elif hasattr(instance, 'config'):
            config = instance.config
        else:
            raise Http404()
        config_archive = config.generate()
        return send_file(
            filename='{0}.tar.gz'.format(config.name),
            contents=config_archive.getvalue(),
        )

    def context_view(self, request, pk):
        instance = get_object_or_404(self.model, pk=pk)
        context = json.dumps(instance.get_context())
        return HttpResponse(context, content_type='application/json')


class BaseForm(forms.ModelForm):
    """
    Adds support for ``OPENWISP_CONTROLLER_DEFAULT_BACKEND``
    """

    if app_settings.DEFAULT_BACKEND:

        def __init__(self, *args, **kwargs):
            # set initial backend value to use the default
            # backend but only for new instances
            if 'instance' not in kwargs:
                kwargs.setdefault('initial', {})
                kwargs['initial'].update({'backend': app_settings.DEFAULT_BACKEND})
            super().__init__(*args, **kwargs)

    class Meta:
        exclude = []
        widgets = {'config': JsonSchemaWidget}


class ConfigForm(AlwaysHasChangedMixin, BaseForm):
    def get_temp_model_instance(self, **options):
        config_model = self.Meta.model
        instance = config_model(**options)
        device_model = config_model.device.field.related_model
        org = Organization.objects.get(pk=self.data['organization'])
        instance.device = device_model(
            name=self.data['name'],
            mac_address=self.data['mac_address'],
            organization=org,
        )
        return instance

    def clean_templates(self):
        config_model = self.Meta.model
        # copy cleaned_data to avoid tampering with it
        data = self.cleaned_data.copy()
        templates = data.pop('templates', [])
        if self.instance._state.adding:
            # when adding self.instance is empty, we need to create a
            # temporary instance that we'll use just for validation
            config = self.get_temp_model_instance(**data)
        else:
            config = self.instance
        if config.backend and templates:
            config_model.clean_templates(
                action='pre_add',
                instance=config,
                sender=config.templates,
                reverse=False,
                model=config.templates.model,
                pk_set=templates,
                # The template validation retrieves the device object
                # from the database. Even if the organization of the device
                # is changed by the user, the validation uses the old
                # organization of the device because the device is not
                # saved yet. The raw POST data is passed here so that
                # validation can be performed using up to date data of
                # the device object.
                raw_data=self.data,
            )
        return templates

    class Meta(BaseForm.Meta):
        model = Config
        widgets = {'config': JsonSchemaWidget, 'context': FlatJsonWidget}
        labels = {'context': _('Configuration Variables')}
        help_texts = {
            'context': _(
                "In this section it's possible to override the default values of "
                "variables defined in templates. If you're not using configuration "
                "variables you can safely ignore this section."
            )
        }


class ConfigInline(
    MultitenantAdminMixin,
    TimeReadonlyAdminMixin,
    SystemDefinedVariableMixin,
    admin.StackedInline,
):
    model = Config
    form = ConfigForm
    verbose_name_plural = _('Device configuration details')
    readonly_fields = ['status', 'system_context']
    fields = [
        'backend',
        'status',
        'templates',
        'system_context',
        'context',
        'config',
        'created',
        'modified',
    ]
    change_select_related = ('device',)
    extra = 0
    verbose_name = _('Configuration')
    verbose_name_plural = verbose_name
    multitenant_shared_relations = ('templates',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(*self.change_select_related)


class DeviceAdmin(MultitenantAdminMixin, BaseConfigAdmin, UUIDAdmin):
    recover_form_template = 'admin/config/device_recover_form.html'
    list_display = [
        'name',
        'backend',
        'group',
        'config_status',
        'mac_address',
        'ip',
        'created',
        'modified',
    ]
    list_filter = [
        'config__status',
        ('organization', MultitenantOrgFilter),
        ('config__templates', MultitenantRelatedOrgFilter),
        ('group', MultitenantRelatedOrgFilter),
        'created',
    ]
    search_fields = [
        'id',
        'name',
        'mac_address',
        'key',
        'model',
        'os',
        'system',
        'devicelocation__location__address',
    ]
    readonly_fields = ['last_ip', 'management_ip', 'uuid']
    autocomplete_fields = ['group']
    fields = [
        'name',
        'organization',
        'mac_address',
        'uuid',
        'key',
        'group',
        'last_ip',
        'management_ip',
        'model',
        'os',
        'system',
        'notes',
        'created',
        'modified',
    ]
    inlines = [ConfigInline]
    conditional_inlines = []

    org_position = 1 if not app_settings.HARDWARE_ID_ENABLED else 2
    list_display.insert(org_position, 'organization')

    if app_settings.CONFIG_BACKEND_FIELD_SHOWN:
        list_filter.insert(1, 'config__backend')
    if app_settings.HARDWARE_ID_ENABLED:
        list_display.insert(1, 'hardware_id')
        search_fields.insert(1, 'hardware_id')
        fields.insert(0, 'hardware_id')
    list_select_related = ('config', 'organization')

    class Media(BaseConfigAdmin.Media):
        js = BaseConfigAdmin.Media.js + [
            f'{prefix}js/tabs.js',
            f'{prefix}js/relevant_templates.js',
        ]

    def get_fields(self, request, obj=None):
        """
        Do not show readonly fields in add form
        """
        fields = list(super().get_fields(request, obj))
        if not obj:
            for field in self.readonly_fields:
                if field in fields:
                    fields.remove(field)
        return fields

    def ip(self, obj):
        mngmt_ip = obj.management_ip if app_settings.MANAGEMENT_IP_DEVICE_LIST else None
        return mngmt_ip or obj.last_ip

    ip.short_description = _('IP address')

    def config_status(self, obj):
        return obj.config.status

    config_status.short_description = _('config status')

    def _get_preview_instance(self, request):
        c = super()._get_preview_instance(request)
        id_ = request.POST.get('id')
        # instantiate new device if it's a new config
        try:
            c.device
        except ObjectDoesNotExist:
            c.device = self.model()
        # fill attributes with up to date data
        c.device.id = id_
        c.device.name = request.POST.get('name')
        c.device.mac_address = request.POST.get('mac_address')
        c.device.key = request.POST.get('key')
        if 'hardware_id' in request.POST:
            c.device.hardware_id = request.POST.get('hardware_id')
        return c

    def get_urls(self):
        urls = [
            path(
                'config/get-relevant-templates/<str:organization_id>/',
                self.admin_site.admin_view(get_relevant_templates),
                name='get_relevant_templates',
            ),
            path(
                'get-template-default-values/',
                self.admin_site.admin_view(get_template_default_values),
                name='get_template_default_values',
            ),
        ] + super().get_urls()
        for inline in self.inlines + self.conditional_inlines:
            try:
                urls.extend(inline(self, self.admin_site).get_urls())
            except AttributeError:
                pass
        return urls

    def get_extra_context(self, pk=None):
        ctx = super().get_extra_context(pk)
        ctx.update(
            {
                'relevant_template_url': reverse(
                    'admin:get_relevant_templates', args=['org_id']
                ),
                'commands_api_endpoint': reverse(
                    'connection_api:device_command_list',
                    args=['00000000-0000-0000-0000-000000000000'],
                ),
            }
        )
        return ctx

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = self.get_extra_context()
        return super().add_view(request, form_url, extra_context)

    def get_inlines(self, request, obj):
        inlines = super().get_inlines(request, obj)
        # this only makes sense in existing devices
        if not obj:
            return inlines
        # add conditional_inlines if condition is met
        inlines = list(inlines)  # copy
        for inline in self.conditional_inlines:
            inline_instance = inline(inline.model, admin.site)
            if inline_instance._get_conditional_queryset(request, obj=obj):
                inlines.append(inline)
        return inlines

    @classmethod
    def add_reversion_following(cls, follow):
        """
        DeviceAdmin is used by other modules that register InlineModelAdmin
        using monkey patching. The default implementation of reversion.register
        ignores such inlines and does not update the "follow" field accordingly.
        This method updates the "follow" fields of the Device model
        by unregistering the Device model from reversion and re-registering it.
        Only the" "follow" option is updated.
        """
        device_reversion_options = reversion.revisions._registered_models[
            reversion.revisions._get_registration_key(Device)
        ]
        following = set(device_reversion_options.follow).union(set(follow))
        reversion.unregister(Device)
        reversion.register(
            model=Device,
            fields=device_reversion_options.fields,
            follow=following,
            format=device_reversion_options.format,
            for_concrete_model=device_reversion_options.for_concrete_model,
            ignore_duplicates=device_reversion_options.ignore_duplicates,
            use_natural_foreign_keys=device_reversion_options.use_natural_foreign_keys,
        )


class CloneOrganizationForm(forms.Form):
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.none(),
        required=False,
        empty_label=_('Shared systemwide (no organization)'),
    )

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop('queryset')
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        org_field = self.fields.get('organization')
        org_field.queryset = queryset
        if not user.is_superuser:
            org_field.empty_label = None


class TemplateForm(BaseForm):
    class Meta(BaseForm.Meta):
        model = Template
        widgets = {'config': JsonSchemaWidget, 'default_values': FlatJsonWidget}
        labels = {'default_values': _('Configuration variables')}
        help_texts = {
            'default_values': _(
                "If you want to use configuration variables in this template, "
                "define them here along with their default values. The content "
                "of each variable can be overridden in each device."
            )
        }


class TemplateAdmin(MultitenantAdminMixin, BaseConfigAdmin, SystemDefinedVariableMixin):
    form = TemplateForm
    list_display = [
        'name',
        'organization',
        'type',
        'backend',
        'default',
        'required',
        'created',
        'modified',
    ]
    list_filter = [
        ('organization', MultitenantOrgFilter),
        'backend',
        'type',
        'default',
        'required',
        'created',
    ]
    search_fields = ['name']
    multitenant_shared_relations = ('vpn',)
    fields = [
        'name',
        'organization',
        'type',
        'backend',
        'vpn',
        'auto_cert',
        'tags',
        'default',
        'required',
        'system_context',
        'default_values',
        'config',
        'created',
        'modified',
    ]
    readonly_fields = ['system_context']

    def clone_selected_templates(self, request, queryset):
        selectable_orgs = None
        user = request.user

        def create_log_entry(user, clone):
            ct = ContentType.objects.get(model='template')
            LogEntry.objects.log_action(
                user_id=user.id,
                content_type_id=ct.pk,
                object_id=clone.pk,
                object_repr=clone.name,
                action_flag=ADDITION,
            )

        if user.is_superuser:
            all_orgs = Organization.objects.all()
            if all_orgs.count() > 1:
                selectable_orgs = all_orgs
        elif len(user.organizations_dict.keys()) > 1:
            selectable_orgs = Organization.objects.filter(
                pk__in=user.organizations_dict.keys()
            )
        if selectable_orgs:
            organization = request.POST.get('organization')
            if organization or organization == '':
                for template in queryset:
                    clone = template.clone(user)
                    clone.organization = None
                    if organization:
                        clone.organization = Organization.objects.get(pk=organization)
                    create_log_entry(user, clone)
                    clone.save()
                self.message_user(
                    request,
                    _('Successfully cloned selected templates.'),
                    messages.SUCCESS,
                )
                return None
            context = {
                'title': _('Clone templates'),
                'queryset': queryset,
                'opts': self.model._meta,
                'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
                'form': CloneOrganizationForm(queryset=selectable_orgs, user=user),
                'changelist_url': (
                    f'{request.resolver_match.app_name}:'
                    f'{request.resolver_match.url_name}'
                ),
            }
            return TemplateResponse(
                request, 'admin/config/clone_template_form.html', context
            )
        else:
            for template in queryset:
                clone = template.clone(user)
                create_log_entry(user, clone)
                clone.save()

    actions = ['clone_selected_templates']


if not app_settings.CONFIG_BACKEND_FIELD_SHOWN:  # pragma: nocover
    DeviceAdmin.list_display.remove('backend')
    TemplateAdmin.list_display.remove('backend')
    TemplateAdmin.list_filter.remove('backend')


class VpnForm(forms.ModelForm):
    """
    Adds support for ``OPENWISP_CONTROLLER_VPN_BACKENDS``
    """

    if app_settings.DEFAULT_VPN_BACKEND:

        def __init__(self, *args, **kwargs):
            if 'initial' in kwargs:
                kwargs['initial'].update({'backend': app_settings.DEFAULT_VPN_BACKEND})
            super().__init__(*args, **kwargs)

    class Meta:
        model = Vpn
        widgets = {'config': JsonSchemaWidget, 'dh': forms.widgets.HiddenInput}
        exclude = []


class VpnAdmin(
    MultitenantAdminMixin, BaseConfigAdmin, UUIDAdmin, SystemDefinedVariableMixin
):
    form = VpnForm
    list_display = ['name', 'organization', 'backend', 'created', 'modified']
    list_filter = [('organization', MultitenantOrgFilter), 'backend', 'created']
    search_fields = ['id', 'name', 'host', 'key']
    readonly_fields = ['id', 'uuid', 'system_context']
    multitenant_shared_relations = ('ca', 'cert', 'subnet')
    autocomplete_fields = ['ip', 'subnet']
    fields = [
        'organization',
        'name',
        'host',
        'uuid',
        'key',
        'backend',
        'ca',
        'cert',
        'subnet',
        'ip',
        'webhook_endpoint',
        'auth_token',
        'notes',
        'dh',
        'system_context',
        'config',
        'created',
        'modified',
    ]

    class Media(BaseConfigAdmin):
        js = list(BaseConfigAdmin.Media.js) + [f'{prefix}js/vpn.js']


class DeviceGroupForm(BaseForm):
    class Meta(BaseForm.Meta):
        model = DeviceGroup
        widgets = {'meta_data': DeviceGroupJsonSchemaWidget}
        labels = {'meta_data': _('Metadata')}
        help_texts = {
            'meta_data': _(
                'Group meta data, use this field to store data which is related'
                'to this group and can be retrieved via the REST API.'
            )
        }


class DeviceGroupAdmin(MultitenantAdminMixin, BaseAdmin):
    form = DeviceGroupForm
    list_display = [
        'name',
        'organization',
        'created',
        'modified',
    ]
    fields = [
        'name',
        'organization',
        'description',
        'meta_data',
        'created',
        'modified',
    ]
    search_fields = ['name', 'description', 'meta_data']
    list_filter = [
        ('organization', MultitenantOrgFilter),
    ]

    class Media:
        css = {'all': (f'{prefix}css/admin.css',)}

    def get_urls(self):
        options = self.model._meta
        url_prefix = f'{options.app_label}_{options.model_name}'
        urls = super().get_urls()
        urls += [
            path(
                f'{options.app_label}/{options.model_name}/ui/schema.json',
                self.admin_site.admin_view(self.schema_view),
                name=f'{url_prefix}_schema',
            ),
        ]
        return urls

    def schema_view(self, request):
        return JsonResponse(app_settings.DEVICE_GROUP_SCHEMA)


admin.site.register(Device, DeviceAdmin)
admin.site.register(Template, TemplateAdmin)
admin.site.register(Vpn, VpnAdmin)
admin.site.register(DeviceGroup, DeviceGroupAdmin)


if getattr(app_settings, 'REGISTRATION_ENABLED', True):
    from openwisp_users.admin import OrganizationAdmin
    from openwisp_utils.admin import AlwaysHasChangedMixin

    class ConfigSettingsForm(AlwaysHasChangedMixin, forms.ModelForm):
        pass

    class ConfigSettingsInline(admin.StackedInline):
        model = OrganizationConfigSettings
        form = ConfigSettingsForm

    OrganizationAdmin.save_on_top = True
    OrganizationAdmin.inlines.insert(0, ConfigSettingsInline)

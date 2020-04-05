import json
import logging

from django import forms
from django.conf import settings
from django.conf.urls import url
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import (
    FieldDoesNotExist,
    ObjectDoesNotExist,
    ValidationError,
)
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from openwisp_controller.config.views import get_default_templates

from openwisp_users.models import Organization
from openwisp_users.multitenancy import (
    MultitenantOrgFilter,
    MultitenantRelatedOrgFilter,
)
from openwisp_utils.admin import (
    AlwaysHasChangedMixin,
    TimeReadonlyAdminMixin,
    UUIDAdmin,
)

from ...admin import MultitenantAdminMixin
from .. import settings as app_settings
from ..utils import send_file
from ..views import schema
from ..widgets import JsonSchemaWidget
from .forms import CloneOrganizationForm

logger = logging.getLogger(__name__)
prefix = 'config/'

if 'reversion' in settings.INSTALLED_APPS:
    from reversion.admin import VersionAdmin as ModelAdmin
else:  # pragma: nocover
    from django.contrib.admin import ModelAdmin


class BaseAdmin(TimeReadonlyAdminMixin, ModelAdmin):
    history_latest_first = True


class BaseConfigAdmin(BaseAdmin):
    preview_template = None
    actions_on_bottom = True
    save_on_top = True

    class Media:
        css = {'all': (static('{0}css/admin.css'.format(prefix)),)}
        js = list(UUIDAdmin.Media.js) + [
            static('{0}js/{1}'.format(prefix, f))
            for f in ('preview.js', 'unsaved_changes.js', 'switcher.js')
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
        if pk:
            ctx['download_url'] = reverse('{0}_download'.format(prefix), args=[pk])
            try:
                has_config = (
                    self.model.__name__ == 'Device'
                    and self.model.objects.get(pk=pk)._has_config()
                )
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
            url(
                r'^download/(?P<pk>[^/]+)/$',
                self.admin_site.admin_view(self.download_view),
                name='{0}_download'.format(url_prefix),
            ),
            url(
                r'^preview/$',
                self.admin_site.admin_view(self.preview_view),
                name='{0}_preview'.format(url_prefix),
            ),
            url(
                r'^(?P<pk>[^/]+)/context\.json$',
                self.admin_site.admin_view(self.context_view),
                name='{0}_context'.format(url_prefix),
            ),
            url(r'^netjsonconfig/schema\.json$', schema, name='schema'),
        ] + super().get_urls()

    def _get_config_model(self):
        model = self.model
        if hasattr(model, 'get_backend_instance'):
            return model
        return model.get_config_model()

    def _get_preview_instance(self, request):
        """
        returns a temporary preview instance used for preview
        """
        kwargs = {}
        config_model = self._get_config_model()
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
        # this object is instanciated only to generate the preview
        # it won't be saved to the database
        instance = config_model(**kwargs)
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
            try:
                templates = template_model.objects.filter(
                    pk__in=template_ids.split(',')
                )
                templates = list(templates)  # evaluating queryset performs query
            except ValidationError as e:
                logger.exception(error_msg, extra={'request': request})
                return HttpResponse(str(e), status=400)
        else:
            templates = None
        if not error:
            backend = instance.get_backend_instance(template_instances=templates)
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
                'admin/%s/%s/preview.html' % (opts.app_label, opts.model_name),
                'admin/%s/preview.html' % opts.app_label,
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
    Adds support for ``NETJSONCONFIG_DEFAULT_BACKEND``
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


class AbstractConfigForm(AlwaysHasChangedMixin, BaseForm):
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
            )
        return templates


class AbstractConfigInline(
    MultitenantAdminMixin, TimeReadonlyAdminMixin, admin.StackedInline
):
    verbose_name_plural = _('Device configuration details')
    readonly_fields = ['status']
    fieldsets = (
        (None, {'fields': ('backend', 'status', 'templates', 'config')}),
        (_('Advanced options'), {'classes': ('collapse',), 'fields': ('context',)}),
        (None, {'fields': ('created', 'modified')}),
    )
    change_select_related = ('device',)
    extra = 0
    verbose_name = _('Configuration')
    verbose_name_plural = verbose_name
    multitenant_shared_relations = ('templates',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(*self.change_select_related)


class AbstractDeviceAdmin(MultitenantAdminMixin, BaseConfigAdmin, UUIDAdmin):
    list_display = ['name', 'backend', 'config_status', 'ip', 'created', 'modified']
    list_filter = [
        ('organization', MultitenantOrgFilter),
        ('config__templates', MultitenantRelatedOrgFilter),
        'config__status',
        'created',
    ]
    search_fields = ['id', 'name', 'mac_address', 'key', 'model', 'os', 'system']
    readonly_fields = ['last_ip', 'management_ip', 'uuid']
    fields = [
        'name',
        'organization',
        'mac_address',
        'uuid',
        'key',
        'last_ip',
        'management_ip',
        'model',
        'os',
        'system',
        'notes',
        'created',
        'modified',
    ]

    org_position = 1 if not app_settings.HARDWARE_ID_ENABLED else 2
    list_display.insert(org_position, 'organization')

    if app_settings.BACKEND_DEVICE_LIST:
        list_filter.insert(1, 'config__backend')
    if app_settings.HARDWARE_ID_ENABLED:
        list_display.insert(1, 'hardware_id')
        search_fields.insert(1, 'hardware_id')
        fields.insert(0, 'hardware_id')
    list_select_related = ('config', 'organization')

    class Media(BaseConfigAdmin.Media):
        js = BaseConfigAdmin.Media.js + ['{0}js/tabs.js'.format(prefix)]

    def ip(self, obj):
        mngmt_ip = obj.management_ip if app_settings.MANAGEMENT_IP_DEVICE_LIST else None
        return mngmt_ip or obj.last_ip

    ip.short_description = _('IP address')

    def config_status(self, obj):
        return obj.config.status

    config_status.short_description = _('config status')

    def _get_preview_instance(self, request):
        c = super()._get_preview_instance(request)
        c.device = self.model(
            id=request.POST.get('id'),
            name=request.POST.get('name'),
            mac_address=request.POST.get('mac_address'),
            key=request.POST.get('key'),
        )
        if 'hardware_id' in request.POST:
            c.device.hardware_id = request.POST.get('hardware_id')
        return c

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
            url(
                r'^config/get-default-templates/(?P<organization_id>[^/]+)/$',
                get_default_templates,
                name='get_default_templates',
            ),
        ] + super().get_urls()

    def get_extra_context(self, pk=None):
        ctx = super().get_extra_context(pk)
        ctx.update({'default_template_urls': self._get_default_template_urls()})
        return ctx

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = self.get_extra_context()
        return super().add_view(request, form_url, extra_context)


if not app_settings.BACKEND_DEVICE_LIST:  # pragma: nocover
    AbstractDeviceAdmin.list_display.remove('backend')
    AbstractDeviceAdmin.list_filter.remove('config__backend')


class AbstractTemplateAdmin(MultitenantAdminMixin, BaseConfigAdmin):
    list_display = [
        'name',
        'organization',
        'type',
        'backend',
        'default',
        'created',
        'modified',
    ]
    list_filter = [
        ('organization', MultitenantOrgFilter),
        'backend',
        'type',
        'default',
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
        'config',
        'created',
        'modified',
    ]

    def clone_selected_templates(self, request, queryset):
        selectable_orgs = None
        if request.user.is_superuser:
            all_orgs = Organization.objects.all()
            if all_orgs.count() > 1:
                selectable_orgs = all_orgs
        elif len(request.user.organizations_pk) > 1:
            selectable_orgs = Organization.objects.filter(
                pk__in=request.user.organizations_pk
            )
        if selectable_orgs:
            if request.POST.get('organization'):
                for template in queryset:
                    clone = template.clone(request.user)
                    clone.organization = Organization.objects.get(
                        pk=request.POST.get('organization')
                    )
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
                'form': CloneOrganizationForm(queryset=selectable_orgs),
            }
            return TemplateResponse(
                request, 'admin/config/clone_template_form.html', context
            )
        else:
            for template in queryset:
                clone = template.clone(request.user)
                clone.save()

    actions = ['clone_selected_templates']


class AbstractVpnForm(forms.ModelForm):
    """
    Adds support for ``NETJSONCONFIG_DEFAULT_BACKEND``
    """

    if app_settings.DEFAULT_VPN_BACKEND:

        def __init__(self, *args, **kwargs):
            if 'initial' in kwargs:
                kwargs['initial'].update({'backend': app_settings.DEFAULT_VPN_BACKEND})
            super().__init__(*args, **kwargs)

    class Meta:
        widgets = {'config': JsonSchemaWidget, 'dh': forms.widgets.HiddenInput}
        exclude = []


class AbstractVpnAdmin(MultitenantAdminMixin, BaseConfigAdmin, UUIDAdmin):
    list_display = ['name', 'organization', 'backend', 'created', 'modified']
    list_filter = [('organization', MultitenantOrgFilter), 'backend', 'created']
    search_fields = ['id', 'name', 'host', 'key']
    readonly_fields = ['id', 'uuid']
    multitenant_shared_relations = ('ca', 'cert')
    fields = [
        'name',
        'host',
        'organization',
        'uuid',
        'key',
        'ca',
        'cert',
        'backend',
        'notes',
        'dh',
        'config',
        'created',
        'modified',
    ]

from datetime import timedelta

import reversion
import swapper
from django import forms
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, resolve
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

from openwisp_users.multitenancy import MultitenantOrgFilter
from openwisp_utils.admin import TimeReadonlyAdminMixin

from ..admin import MultitenantAdminMixin
from ..config.admin import DeviceAdmin
from .commands import COMMANDS
from .schema import schema
from .widgets import CommandSchemaWidget, CredentialsSchemaWidget

Credentials = swapper.load_model('connection', 'Credentials')
DeviceConnection = swapper.load_model('connection', 'DeviceConnection')
Command = swapper.load_model('connection', 'Command')


class CredentialsForm(forms.ModelForm):
    class Meta:
        exclude = []
        widgets = {'params': CredentialsSchemaWidget}


class CommandForm(forms.ModelForm):
    class Meta:
        exclude = []
        widgets = {'input': CommandSchemaWidget}


@admin.register(Credentials)
class CredentialsAdmin(MultitenantAdminMixin, TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = (
        'name',
        'organization',
        'connector',
        'auto_add',
        'created',
        'modified',
    )
    list_filter = [('organization', MultitenantOrgFilter), 'connector']
    list_select_related = ('organization',)
    form = CredentialsForm
    fields = [
        'connector',
        'name',
        'organization',
        'auto_add',
        'params',
        'created',
        'modified',
    ]

    def get_urls(self):
        options = getattr(self.model, '_meta')
        url_prefix = f'{options.app_label}_{options.model_name}'
        return [
            path(
                'ui/schema.json',
                self.admin_site.admin_view(self.schema_view),
                name=f'{url_prefix}_schema',
            )
        ] + super().get_urls()

    def schema_view(self, request):
        return JsonResponse(schema)


class DeviceConnectionInline(MultitenantAdminMixin, admin.StackedInline):
    model = DeviceConnection
    verbose_name = _('Credentials')
    verbose_name_plural = verbose_name
    exclude = ['params', 'created', 'modified']
    readonly_fields = ['is_working', 'failure_reason', 'last_attempt']
    extra = 0

    multitenant_shared_relations = ('credentials',)

    def get_queryset(self, request):
        """
        Override MultitenantAdminMixin.get_queryset() because it breaks
        """
        return super(admin.StackedInline, self).get_queryset(request)


class CommandInline(admin.StackedInline):
    model = Command
    verbose_name = _('Recent Commands')
    verbose_name_plural = verbose_name
    fields = ['status', 'type', 'input_data', 'output', 'created', 'modified']
    readonly_fields = ['input_data']
    # hack for openwisp-monitoring integration
    # TODO: remove when this issue solved:
    # https://github.com/theatlantic/django-nested-admin/issues/128#issuecomment-665833142
    sortable_options = {'disabled': True}

    def get_queryset(self, request, select_related=True):
        """
        Return recent commands for this device
        (created within the last 7 days)
        """
        qs = super().get_queryset(request)
        resolved = resolve(request.path_info)
        if 'object_id' in resolved.kwargs:
            seven_days = localtime() - timedelta(days=7)
            qs = qs.filter(
                device_id=resolved.kwargs['object_id'], created__gte=seven_days
            ).order_by('-created')
        if select_related:
            qs = qs.select_related()
        return qs

    def input_data(self, obj):
        return obj.input_data

    input_data.short_description = _('input')

    def _get_conditional_queryset(self, request, obj, select_related=False):
        return self.get_queryset(request, select_related=select_related).exists()

    def has_delete_permission(self, request, obj):
        return False

    def has_add_permission(self, request, obj):
        return False

    def has_change_permission(self, request, obj):
        return False


class CommandWritableInline(admin.StackedInline):
    model = Command
    extra = 1
    form = CommandForm
    fields = ['type', 'input']

    def get_queryset(self, request, select_related=True):
        return self.model.objects.none()

    def _get_conditional_queryset(self, request, obj, select_related=False):
        return bool(obj)

    def get_urls(self):
        options = self.model._meta
        url_prefix = f'{options.app_label}_{options.model_name}'
        return [
            path(
                f'{options.app_label}/{options.model_name}/ui/schema.json',
                self.admin_site.admin_view(self.schema_view),
                name=f'{url_prefix}_schema',
            ),
        ]

    def schema_view(self, request):
        result = {}
        for key, value in COMMANDS.items():
            result.update({key: value['schema']})
        return JsonResponse(result)


DeviceAdmin.inlines += [DeviceConnectionInline]
reversion.register(model=DeviceConnection, follow=['device'])
DeviceAdmin.conditional_inlines += [
    CommandWritableInline,
    # this inline must come after CommandWritableInline
    # or the JS logic will not work
    CommandInline,
]
DeviceAdmin.add_reversion_following(follow=['deviceconnection_set'])

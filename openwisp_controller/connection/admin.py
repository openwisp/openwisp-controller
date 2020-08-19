import swapper
from django import forms
from django.conf.urls import url
from django.contrib import admin
from django.http import JsonResponse
from django.utils.translation import ugettext_lazy as _

from openwisp_users.multitenancy import MultitenantOrgFilter
from openwisp_utils.admin import TimeReadonlyAdminMixin

from ..admin import MultitenantAdminMixin
from ..config.admin import DeviceAdmin
from .schema import schema
from .widgets import CredentialsSchemaWidget

Credentials = swapper.load_model('connection', 'Credentials')
DeviceConnection = swapper.load_model('connection', 'DeviceConnection')


class CredentialsForm(forms.ModelForm):
    class Meta:
        exclude = []
        widgets = {'params': CredentialsSchemaWidget}


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
            url(
                r'^ui/schema.json$',
                self.admin_site.admin_view(self.schema_view),
                name=f'{url_prefix}_schema',
            ),
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


DeviceAdmin.inlines += [DeviceConnectionInline]

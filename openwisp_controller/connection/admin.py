from django.contrib import admin

from openwisp_utils.admin import MultitenantOrgFilter, TimeReadonlyAdminMixin

from ..admin import MultitenantAdminMixin
from ..config.admin import DeviceAdmin
from .models import Credentials, DeviceConnection, DeviceIp


@admin.register(Credentials)
class CredentialsAdmin(MultitenantAdminMixin, TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'organization', 'connector', 'created', 'modified')
    list_filter = [('organization', MultitenantOrgFilter),
                   'connector']
    list_select_related = ('organization',)


class DeviceIpInline(admin.TabularInline):
    model = DeviceIp
    exclude = ('created', 'modified')
    extra = 0

    def get_queryset(self, request):
        qs = super(DeviceIpInline, self).get_queryset(request)
        return qs.order_by('priority')


class DeviceConnectionInline(MultitenantAdminMixin, admin.StackedInline):
    model = DeviceConnection
    exclude = ['params', 'created', 'modified']
    readonly_fields = ['is_working', 'failure_reason', 'last_attempt']
    extra = 0

    multitenant_shared_relations = ('credentials',)

    def get_queryset(self, request):
        """
        Override MultitenantAdminMixin.get_queryset() because it breaks
        """
        return super(admin.StackedInline, self).get_queryset(request)


DeviceAdmin.inlines += [DeviceConnectionInline, DeviceIpInline]

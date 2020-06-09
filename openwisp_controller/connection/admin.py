from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from openwisp_users.multitenancy import MultitenantOrgFilter
from openwisp_utils.admin import TimeReadonlyAdminMixin

from ..admin import MultitenantAdminMixin
from ..config.admin import DeviceAdmin
from .models import Credentials, DeviceConnection


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

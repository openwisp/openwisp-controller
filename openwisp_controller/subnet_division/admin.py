from django.contrib import admin
from django.urls import reverse
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from openwisp_ipam.admin import IpAddressAdmin as BaseIpAddressAdmin
from openwisp_ipam.admin import SubnetAdmin as BaseSubnetAdmin
from swapper import load_model

from openwisp_controller.config.admin import DeviceAdmin
from openwisp_users.multitenancy import MultitenantAdminMixin, MultitenantOrgFilter
from openwisp_utils.admin import HelpTextStackedInline, TimeReadonlyAdminMixin

from . import settings as app_settings
from .filters import DeviceFilter, SubnetFilter, SubnetListFilter

SubnetDivisionRule = load_model('subnet_division', 'SubnetDivisionRule')
SubnetDivisionIndex = load_model('subnet_division', 'SubnetDivisionIndex')
Subnet = load_model('openwisp_ipam', 'Subnet')
IpAddress = load_model('openwisp_ipam', 'IpAddress')
Device = load_model('config', 'Device')


class SubnetDivisionRuleInlineAdmin(
    MultitenantAdminMixin, TimeReadonlyAdminMixin, HelpTextStackedInline
):
    model = SubnetDivisionRule
    extra = 0
    help_text = {
        'text': _(
            'Please keep in mind that once the subnet division rule is created '
            'changing changing "Size", "Number of Subnets" or decreasing '
            '"Number of IPs" will not be possible.'
        ),
        'documentation_url': (
            'https://github.com/openwisp/openwisp-controller'
            '#limitations-of-subnet-division'
        ),
    }

    class Media:
        js = ['admin/js/jquery.init.js', 'subnet-division/js/subnet-division.js']


# Monkey patching DeviceAdmin to allow filtering using subnet
DeviceAdmin.list_filter.append(SubnetFilter)

# NOTE: Monkey patching SubnetAdmin didn't work for adding readonly_field
# to change_view because of TimeReadonlyAdminMixin.

admin.site.unregister(Subnet)
admin.site.unregister(IpAddress)


@admin.register(Subnet)
class SubnetAdmin(BaseSubnetAdmin):
    list_filter = BaseSubnetAdmin.list_filter + [DeviceFilter]
    inlines = [SubnetDivisionRuleInlineAdmin] + BaseSubnetAdmin.inlines

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        subnet_division_index_qs = (
            SubnetDivisionIndex.objects.filter(
                subnet_id__in=qs.filter(master_subnet__isnull=False).values('id'),
                ip__isnull=True,
            )
            .select_related('config__device')
            .values_list('subnet_id', 'config__device__name')
        )
        self._lookup = {}
        for subnet_id, device_name in subnet_division_index_qs:
            self._lookup[subnet_id] = device_name

        if app_settings.HIDE_GENERATED_SUBNETS:
            qs = qs.exclude(
                id__in=SubnetDivisionIndex.objects.filter(
                    ip__isnull=True, subnet__isnull=False
                ).values_list('subnet_id')
            )

        return qs

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj is not None and 'related_device' not in fields:
            fields = ('related_device',) + fields
        return fields

    def get_list_display(self, request):
        fields = super().get_list_display(request)
        return fields + ['related_device']

    def related_device(self, obj):
        app_label = Device._meta.app_label
        url = reverse(f'admin:{app_label}_device_changelist')
        if obj.master_subnet is None:
            msg_string = _('See all devices')
            return mark_safe(
                f'<a href="{url}?subnet={str(obj.subnet)}">{msg_string}</a>'
            )
        else:
            if obj.id in self._lookup:
                device = self._lookup[obj.id]
                return mark_safe(
                    f'<a href="{url}?subnet={str(obj.subnet)}">{device}</a>'
                )

    def has_change_permission(self, request, obj=None):
        permission = super().has_change_permission(request, obj)
        if not obj:
            return permission
        automated = SubnetDivisionIndex.objects.filter(subnet_id=obj.id).exists()
        return permission and not automated


@admin.register(IpAddress)
class IpAddressAdmin(BaseIpAddressAdmin):
    list_filter = [
        ('subnet', SubnetListFilter),
        ('subnet__organization', MultitenantOrgFilter),
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if app_settings.HIDE_GENERATED_SUBNETS:
            qs = qs.exclude(
                id__in=SubnetDivisionIndex.objects.filter(ip__isnull=False).values_list(
                    'ip_id'
                )
            )
        return qs

    def has_change_permission(self, request, obj=None):
        permission = super().has_change_permission(request, obj)
        if not obj:
            return permission
        automated = SubnetDivisionIndex.objects.filter(ip_id=obj.id).exists()
        return permission and not automated

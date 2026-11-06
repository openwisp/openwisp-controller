from django.contrib import admin, messages
from django.contrib.admin.actions import delete_selected as django_delete_selected
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from openwisp_ipam.admin import IpAddressAdmin as BaseIpAddressAdmin
from openwisp_ipam.admin import SubnetAdmin as BaseSubnetAdmin
from swapper import load_model

from openwisp_controller.config.admin import DeviceAdmin
from openwisp_users.multitenancy import MultitenantAdminMixin
from openwisp_utils.admin import HelpTextStackedInline, TimeReadonlyAdminMixin

from . import settings as app_settings
from .filters import (
    DeviceFilter,
    DeviceSubnetDivisionRuleFilter,
    SubnetDivisionRuleFilter,
    SubnetFilter,
    VpnFilter,
)

SubnetDivisionRule = load_model("subnet_division", "SubnetDivisionRule")
SubnetDivisionIndex = load_model("subnet_division", "SubnetDivisionIndex")
Subnet = load_model("openwisp_ipam", "Subnet")
IpAddress = load_model("openwisp_ipam", "IpAddress")
Device = load_model("config", "Device")


class SubnetDivisionRuleInlineAdmin(
    MultitenantAdminMixin, TimeReadonlyAdminMixin, HelpTextStackedInline
):
    model = SubnetDivisionRule
    extra = 0
    help_text = {
        "text": _(
            "Please keep in mind that once the subnet division rule is created "
            'changing "Size", "Number of Subnets" or decreasing '
            '"Number of IPs" will not be possible.'
        ),
        "documentation_url": (
            "https://openwisp.io/docs/stable/controller/user/subnet-division-rules.html"
            "#limitations-of-subnet-division-rules"
        ),
    }

    class Media:
        js = ["admin/js/jquery.init.js", "subnet-division/js/subnet-division.js"]


@admin.register(SubnetDivisionRule)
class SubnetDivisionRuleAdmin(
    MultitenantAdminMixin, TimeReadonlyAdminMixin, admin.ModelAdmin
):
    list_display = ["label", "organization", "type", "master_subnet"]
    list_filter = ["type"]
    search_fields = ["label"]
    actions = ["delete_selected"]
    # caps how many affected-device links are listed in the bulk error message
    in_use_links_limit = 10

    def _affected_devices_url(self, obj):
        return reverse("admin:config_device_changelist") + (
            f"?subnet_division_rule={obj.pk}"
        )

    def _in_use_error(self, request, obj):
        messages.error(
            request,
            format_html(
                _(
                    "This subnet division rule is used by device "
                    "configurations and cannot be deleted. "
                    '<a href="{}">View affected devices</a>'
                ),
                self._affected_devices_url(obj),
            ),
        )

    def _bulk_in_use_error(self, request, queryset):
        """Reports in-use rules with a link to their affected devices.

        The list of rules is bounded by the user's selection and further
        capped, so the message never embeds an unbounded device list.
        """
        rules = list(
            queryset.filter(subnetdivisionindex__config_id__isnull=False)
            .distinct()
            .order_by("label")[: self.in_use_links_limit + 1]
        )
        truncated = len(rules) > self.in_use_links_limit
        rules = rules[: self.in_use_links_limit]
        links = format_html_join(
            ", ",
            '<a href="{}">{}</a>',
            ((self._affected_devices_url(rule), rule.label) for rule in rules),
        )
        message = format_html(
            _(
                "The following subnet division rules are used by device "
                "configurations and cannot be deleted: {}"
            ),
            links,
        )
        if truncated:
            message = format_html(
                "{} {}",
                message,
                _("Only the first %(limit)s rules are listed.")
                % {"limit": self.in_use_links_limit},
            )
        messages.error(request, message)

    def delete_view(self, request, object_id, extra_context=None):
        try:
            # The deletion and its log entry are wrapped in a transaction so
            # that a refusal rolls back both before the error is reported.
            with transaction.atomic():
                return super().delete_view(
                    request, object_id, extra_context=extra_context
                )
        except ValidationError as e:
            if getattr(e, "code", None) != "subnet_division_rule_in_use":
                raise
            obj = self.get_object(request, object_id)
            self._in_use_error(request, obj)
            return HttpResponseRedirect(
                reverse("admin:subnet_division_subnetdivisionrule_changelist")
            )

    @admin.action(
        description=django_delete_selected.short_description, permissions=["delete"]
    )
    def delete_selected(self, request, queryset):
        if not self.has_delete_permission(request):
            raise PermissionDenied
        try:
            with transaction.atomic():
                return django_delete_selected(self, request, queryset)
        except ValidationError as e:
            if getattr(e, "code", None) != "subnet_division_rule_in_use":
                raise
            self._bulk_in_use_error(request, queryset)


# Monkey patching DeviceAdmin to allow filtering using subnet
DeviceAdmin.list_filter.append(SubnetFilter)
DeviceAdmin.list_filter.append(DeviceSubnetDivisionRuleFilter)

# NOTE: Monkey patching SubnetAdmin didn't work for adding readonly_field
# to change_view because of TimeReadonlyAdminMixin.

admin.site.unregister(Subnet)
admin.site.unregister(IpAddress)


@admin.register(Subnet)
class SubnetAdmin(BaseSubnetAdmin):
    list_filter = BaseSubnetAdmin.list_filter + [
        SubnetDivisionRuleFilter,
        VpnFilter,
        DeviceFilter,
    ]
    inlines = [SubnetDivisionRuleInlineAdmin] + list(BaseSubnetAdmin.inlines)
    list_display = BaseSubnetAdmin.list_display
    list_display.insert(list_display.index("created"), "related_device")

    def delete_view(self, request, object_id, extra_context=None):
        # Deleting a subnet cascades to its subnet division rules, which
        # refuse the deletion when they are in use. Without this the
        # ValidationError would propagate out of the request as a server
        # error instead of being reported to the user.
        try:
            with transaction.atomic():
                return super().delete_view(
                    request, object_id, extra_context=extra_context
                )
        except ValidationError as e:
            if getattr(e, "code", None) != "subnet_division_rule_in_use":
                raise
            messages.error(
                request,
                _(
                    "This subnet cannot be deleted because one of its subnet "
                    "division rules is used by device configurations."
                ),
            )
            return HttpResponseRedirect(
                reverse(
                    f"admin:{Subnet._meta.app_label}_subnet_change", args=[object_id]
                )
            )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        subnet_division_index_qs = (
            SubnetDivisionIndex.objects.filter(
                subnet_id__in=qs.filter(master_subnet__isnull=False).values("id"),
                ip__isnull=True,
            )
            .select_related("config__device")
            .values_list("subnet_id", "config__device__name")
        )
        self._lookup = {}
        for subnet_id, device_name in subnet_division_index_qs:
            self._lookup[subnet_id] = device_name

        if app_settings.HIDE_GENERATED_SUBNETS:
            qs = qs.exclude(
                id__in=SubnetDivisionIndex.objects.filter(
                    ip__isnull=True, subnet__isnull=False
                ).values_list("subnet_id")
            )

        return qs

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj is not None and "related_device" not in fields:
            fields = ("related_device",) + fields
        return fields

    def related_device(self, obj):
        app_label = Device._meta.app_label
        url = reverse(f"admin:{app_label}_device_changelist")
        if obj.master_subnet is None:
            return format_html(
                '<a href="{}?subnet={}">{}</a>',
                url,
                str(obj.subnet),
                _("See all devices"),
            )
        else:
            if obj.id in self._lookup:
                return format_html(
                    '<a href="{}?subnet={}">{}</a>',
                    url,
                    str(obj.subnet),
                    self._lookup[obj.id],
                )

    def has_change_permission(self, request, obj=None):
        permission = super().has_change_permission(request, obj)
        if not obj:
            return permission
        automated = SubnetDivisionIndex.objects.filter(subnet_id=obj.id).exists()
        return permission and not automated


@admin.register(IpAddress)
class IpAddressAdmin(BaseIpAddressAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if app_settings.HIDE_GENERATED_SUBNETS:
            qs = qs.exclude(
                id__in=SubnetDivisionIndex.objects.filter(ip__isnull=False).values_list(
                    "ip_id"
                )
            )
        return qs

    def has_change_permission(self, request, obj=None):
        permission = super().has_change_permission(request, obj)
        if not obj:
            return permission
        automated = SubnetDivisionIndex.objects.filter(ip_id=obj.id).exists()
        return permission and not automated

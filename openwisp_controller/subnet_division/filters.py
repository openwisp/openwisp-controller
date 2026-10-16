import uuid

from django.contrib import admin, messages
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_utils.admin_theme.filters import AutocompleteFilter, SimpleInputFilter

from . import settings as app_settings

SubnetDivisionIndex = load_model("subnet_division", "SubnetDivisionIndex")
SubnetDivisionRule = load_model("subnet_division", "SubnetDivisionRule")
Subnet = load_model("openwisp_ipam", "Subnet")
Vpn = load_model("config", "Vpn")


class SubnetDivisionRuleFilter(admin.SimpleListFilter):
    title = _("Subnet division rule type")
    parameter_name = "rule_type"

    def lookups(self, request, model_admin):
        return SubnetDivisionRule.type.field.get_choices(include_blank=False)

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(
                id__in=SubnetDivisionRule.objects.filter(type=self.value()).values_list(
                    "master_subnet_id"
                )
            )


class SubnetFilter(SimpleInputFilter):
    parameter_name = "subnet"
    title = _("subnet")

    def queryset(self, request, queryset):
        if self.value() is not None:
            master_subnet_key = (
                "config__subnetdivisionindex__subnet__master_subnet__subnet"
            )
            return queryset.filter(
                Q(**{master_subnet_key: self.value()})
                | Q(config__subnetdivisionindex__subnet__subnet=self.value())
            ).distinct()


class DeviceFilter(SimpleInputFilter):
    """
    Filters Subnet queryset for input device name
    using SubnetDivisionIndex
    """

    parameter_name = "device"
    title = _("device name")

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(
                id__in=SubnetDivisionIndex.objects.filter(
                    config__device__name=self.value()
                ).values_list("subnet_id")
            )


class DeviceSubnetDivisionRuleFilter(admin.SimpleListFilter):
    title = _("subnet division rule")
    parameter_name = "subnet_division_rule"

    def lookups(self, request, model_admin):
        device_qs = model_admin.get_queryset(request)
        org_ids = set(device_qs.values_list("organization_id", flat=True).distinct())
        return (
            SubnetDivisionRule.objects.filter(
                Q(organization_id__in=org_ids) | Q(organization_id__isnull=True)
            )
            .values_list("id", "label")
            .order_by("label")
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value is None:
            return queryset
        try:
            uuid.UUID(value)
        except (AttributeError, ValueError):
            messages.error(request, _("Invalid subnet division rule ID."))
            return queryset
        return queryset.filter(config__subnetdivisionindex__rule_id=value).distinct()


class VpnFilter(AutocompleteFilter):
    """
    Filters Subnet by VPN
    autocomplete on inverse relation
    """

    title = _("VPN Server")
    field_name = "vpn"
    parameter_name = "vpn"


class SubnetListFilter(admin.RelatedFieldListFilter):
    def field_choices(self, field, request, model_admin):
        if app_settings.HIDE_GENERATED_SUBNETS and field.name == "subnet":
            return field.get_choices(
                include_blank=False,
                limit_choices_to={
                    "id__in": Subnet.objects.exclude(
                        id__in=SubnetDivisionIndex.objects.filter(
                            ip__isnull=True, subnet__isnull=False
                        ).values_list("subnet_id")
                    )
                },
            )
        choices = super().field_choices(field, request, model_admin)
        return choices

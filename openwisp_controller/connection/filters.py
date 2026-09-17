from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_users.multitenancy import MultitenantRelatedOrgFilter

from .commands import get_command_choices


class GroupFilter(MultitenantRelatedOrgFilter):
    field_name = "group"
    parameter_name = "group_id"
    title = _("group")


class LocationFilter(MultitenantRelatedOrgFilter):
    field_name = "location"
    parameter_name = "location_id"
    title = _("location")


class TypeFilter(admin.SimpleListFilter):
    title = _("type")
    parameter_name = "type"

    def lookups(self, request, model_admin):
        if request.user.is_superuser:
            return list(get_command_choices())
        Command = load_model("connection", "Command")
        allowed = {}
        for organization_id in request.user.organizations_managed:
            allowed.update(
                Command.get_org_allowed_commands(organization_id=organization_id)
            )
        return list(allowed.items())

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(type=self.value())
        return queryset

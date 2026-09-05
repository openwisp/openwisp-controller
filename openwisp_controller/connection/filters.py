from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_users.multitenancy import MultitenantRelatedOrgFilter


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
        BatchCommand = load_model("connection", "BatchCommand")
        qs = BatchCommand.objects.all()
        if not request.user.is_superuser:
            qs = qs.filter(organization_id__in=request.user.organizations_managed)
        types = qs.values_list("type", flat=True).distinct()
        choices = dict(BatchCommand._meta.get_field("type").choices)
        return [(t, choices.get(t, t)) for t in types]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(type=self.value())
        return queryset

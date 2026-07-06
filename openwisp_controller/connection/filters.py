from django.utils.translation import gettext_lazy as _

from openwisp_users.multitenancy import MultitenantRelatedOrgFilter


class GroupFilter(MultitenantRelatedOrgFilter):
    field_name = "group"
    parameter_name = "group_id"
    title = _("group")


class LocationFilter(MultitenantRelatedOrgFilter):
    field_name = "location"
    parameter_name = "location_id"
    title = _("location")

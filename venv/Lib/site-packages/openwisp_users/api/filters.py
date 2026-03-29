from django_filters import rest_framework as filters

from .mixins import (
    FilterDjangoByOrgManaged,
    FilterDjangoByOrgMembership,
    FilterDjangoByOrgOwned,
)


class BaseOrganizationFilter:
    """
    A class that provides organization and organization slug filter fields
    """

    class Meta:
        fields = ["organization", "organization_slug"]


class OrganizationMembershipFilter(BaseOrganizationFilter, FilterDjangoByOrgMembership):
    """
    A Django filter class that can be used in various OpenWISP API views
    to filter relation fields based on the user organization membership
    """

    organization_slug = filters.CharFilter(field_name="organization__slug")


class OrganizationManagedFilter(BaseOrganizationFilter, FilterDjangoByOrgManaged):
    """
    A Django Filter class that can be used in various OpenWISP API views
    to filter relation fields based on the organization managed by the user
    """

    organization_slug = filters.CharFilter(field_name="organization__slug")


class OrganizationOwnedFilter(BaseOrganizationFilter, FilterDjangoByOrgOwned):
    """
    A Django Filter class that can be used in various OpenWISP API views
    to filter relation fields based on the organization owned by the user
    """

    organization_slug = filters.CharFilter(field_name="organization__slug")

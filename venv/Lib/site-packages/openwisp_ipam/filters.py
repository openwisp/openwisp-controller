from django.utils.translation import gettext_lazy as _
from openwisp_users.multitenancy import MultitenantRelatedOrgFilter
from swapper import load_model

Subnet = load_model("openwisp_ipam", "Subnet")


class SubnetFilter(MultitenantRelatedOrgFilter):
    field_name = "subnet"
    parameter_name = "subnet_id"
    title = _("subnet")


class SubnetOrganizationFilter(MultitenantRelatedOrgFilter):
    parameter_name = "subnet__organization"
    rel_model = Subnet

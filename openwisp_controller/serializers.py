from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer


class BaseSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    """BaseSerializer for most API endpoints.

    - FilterSerializerByOrgManaged: for multi-tenancy
    - ValidatedModelSerializer: for model validation
    """

    pass

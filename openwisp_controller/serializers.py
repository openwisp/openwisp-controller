from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer


class BaseSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    pass

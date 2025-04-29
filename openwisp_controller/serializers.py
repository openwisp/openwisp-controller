from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer


class ValidatedDeviceIdSerializer(ValidatedModelSerializer):
    def validate(self, data):
        """
        Adds "device_id" to the data dictionary which
        is going to be used to create the temporary
        instance used for validation
        """
        for key in ['device', 'device_id']:
            if key in self.context:
                data[key] = self.context[key]
        return super().validate(data)


class BaseSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    """
    TODO
    """

    pass


class BaseDeviceIdSerializer(FilterSerializerByOrgManaged, ValidatedDeviceIdSerializer):
    """
    TODO
    """

    pass


class DeviceContextMixin:
    """
    TODO
    """

    def get_object(self):
        obj = super().get_object()
        self.object = obj
        return obj

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['device'] = self.object
        return context

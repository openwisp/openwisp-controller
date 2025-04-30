from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer


class ValidatedDeviceIdSerializer(ValidatedModelSerializer):
    pass
    # def validate(self, data):
    #     """Adds "device" to the data dictionary.
    #
    #     Used to satisfy validation needs."""
    #     # for key in ['device', 'device_id']:
    #     #     if key in self.context:
    #     #         data[key] = self.context[key]
    #     if 'device' in self.context:
    #         data['device'] = self.context['device']
    #     data = super().validate(data)
    #     data.pop('device', None)
    #     return data


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
    """Adds the device object to the serializer context."""

    def get_object(self):
        obj = super().get_object()
        self.object = obj
        return obj

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['device'] = self.object
        return context

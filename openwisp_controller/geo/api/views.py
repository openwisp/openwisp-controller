from django.core.exceptions import ObjectDoesNotExist
from rest_framework import generics
from rest_framework.permissions import BasePermission
from rest_framework_gis import serializers as gis_serializers
from swapper import load_model

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')


class DevicePermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.query_params.get('key') == obj.key


class LocationSerializer(gis_serializers.GeoFeatureModelSerializer):
    class Meta:
        model = Location
        geo_field = 'geometry'
        fields = ('name', 'geometry')
        read_only_fields = ('name',)


class DeviceLocationView(generics.RetrieveUpdateAPIView):
    serializer_class = LocationSerializer
    permission_classes = (DevicePermission,)
    queryset = Device.objects.select_related(
        'devicelocation', 'devicelocation__location'
    )

    def get_location(self, device):
        try:
            return device.devicelocation.location
        except ObjectDoesNotExist:
            return None

    def get_object(self, *args, **kwargs):
        device = super().get_object()
        location = self.get_location(device)
        if location:
            return location
        # if no location present, automatically create it
        return self.create_location(device)

    def create_location(self, device):
        location = Location(
            name=device.name,
            type='outdoor',
            organization=device.organization,
            is_mobile=True,
        )
        location.full_clean()
        location.save()
        dl = DeviceLocation(content_object=device, location=location)
        dl.full_clean()
        dl.save()
        return location


device_location = DeviceLocationView.as_view()

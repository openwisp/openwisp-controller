from django.urls import reverse
from rest_framework.serializers import IntegerField, SerializerMethodField
from rest_framework_gis import serializers as gis_serializers
from swapper import load_model

from openwisp_utils.api.serializers import ValidatedModelSerializer

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')


class LocationSerializer(gis_serializers.GeoFeatureModelSerializer):
    class Meta:
        model = Location
        geo_field = 'geometry'
        fields = ('name', 'geometry')
        read_only_fields = ('name',)


class LocationDeviceSerializer(ValidatedModelSerializer):
    admin_edit_url = SerializerMethodField('get_admin_edit_url')

    def get_admin_edit_url(self, obj):
        return self.context['request'].build_absolute_uri(
            reverse(f'admin:{obj._meta.app_label}_device_change', args=(obj.id,))
        )

    class Meta:
        model = Device
        fields = '__all__'


class GeoJsonLocationSerializer(gis_serializers.GeoFeatureModelSerializer):
    device_count = IntegerField()

    class Meta:
        model = Location
        geo_field = 'geometry'
        fields = '__all__'

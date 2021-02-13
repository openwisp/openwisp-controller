from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from django.urls import reverse
from rest_framework import generics, pagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.serializers import IntegerField, SerializerMethodField
from rest_framework_gis import serializers as gis_serializers
from rest_framework_gis.pagination import GeoJsonPagination
from swapper import load_model

from openwisp_users.api.mixins import FilterByOrganizationManaged, FilterByParentManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

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


class DeviceSerializer(ValidatedModelSerializer):
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


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


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


class GeoJsonLocationList(FilterByOrganizationManaged, generics.ListAPIView):
    GeoJsonPagination.page_size = 1000
    permission_classes = (IsAuthenticated,)
    pagination_class = GeoJsonPagination
    queryset = Location.objects.filter(devicelocation__isnull=False).annotate(
        device_count=Count('devicelocation')
    )
    serializer_class = GeoJsonLocationSerializer


class LocationDeviceList(FilterByParentManaged, generics.ListAPIView):
    serializer_class = DeviceSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = ListViewPagination
    queryset = Device.objects.none()

    def get_parent_queryset(self):
        qs = Location.objects.filter(pk=self.kwargs['pk'])
        return qs

    def get_queryset(self):
        super().get_queryset()
        qs = Device.objects.filter(devicelocation__location_id=self.kwargs['pk'])
        return qs


device_location = DeviceLocationView.as_view()
geojson = GeoJsonLocationList.as_view()
location_device_list = LocationDeviceList.as_view()

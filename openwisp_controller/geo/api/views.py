from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from django_filters import rest_framework as filters
from rest_framework import generics, pagination
from rest_framework.permissions import BasePermission
from rest_framework_gis.pagination import GeoJsonPagination
from swapper import load_model

from openwisp_users.api.mixins import FilterByOrganizationManaged, FilterByParentManaged

from .serializers import (
    GeoJsonLocationSerializer,
    LocationDeviceSerializer,
    LocationSerializer,
)

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')


class DevicePermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        # checks for presence of key attribute first
        # because in the browsable UI this method is
        # getting passed also Location instances,
        # which do not have the key attribute
        return hasattr(obj, 'key') and request.query_params.get('key') == obj.key


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


class GeoJsonLocationListPagination(GeoJsonPagination):
    page_size = 1000


class GeoJsonLocationFilter(filters.FilterSet):
    organization_slug = filters.CharFilter(field_name='organization__slug')

    class Meta:
        model = Location
        fields = ['organization_slug']


class GeoJsonLocationList(FilterByOrganizationManaged, generics.ListAPIView):
    queryset = Location.objects.filter(devicelocation__isnull=False).annotate(
        device_count=Count('devicelocation')
    )
    serializer_class = GeoJsonLocationSerializer
    pagination_class = GeoJsonLocationListPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = GeoJsonLocationFilter


class LocationDeviceList(FilterByParentManaged, generics.ListAPIView):
    serializer_class = LocationDeviceSerializer
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

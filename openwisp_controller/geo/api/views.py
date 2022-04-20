from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Count
from django.http import Http404
from django_filters import rest_framework as filters
from rest_framework import generics, pagination, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission
from rest_framework.request import clone_request
from rest_framework.response import Response
from rest_framework_gis.pagination import GeoJsonPagination
from swapper import load_model

from openwisp_users.api.mixins import FilterByOrganizationManaged, FilterByParentManaged

from ...mixins import ProtectedAPIMixin
from .serializers import (
    DeviceCoordinatesSerializer,
    DeviceLocationSerializer,
    FloorPlanSerializer,
    GeoJsonLocationSerializer,
    LocationDeviceSerializer,
    LocationSerializer,
)

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')
FloorPlan = load_model('geo', 'FloorPlan')


class DevicePermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        # checks for presence of key attribute first
        # because in the browsable UI this method is
        # getting passed also Location instances,
        # which do not have the key attribute
        return hasattr(obj, 'key') and request.query_params.get('key') == obj.key


class BaseOrganizationSlugFilter(filters.FilterSet):
    organization_slug = filters.CharFilter(field_name='organization__slug')

    class Meta:
        fields = ['organization_slug']


class LocationOrganizationSlugFilter(BaseOrganizationSlugFilter):
    class Meta(BaseOrganizationSlugFilter.Meta):
        model = Location
        fields = BaseOrganizationSlugFilter.Meta.fields + ['is_mobile', 'type']


class FloorPlanOrganizationSlugFilter(BaseOrganizationSlugFilter):
    class Meta(BaseOrganizationSlugFilter.Meta):
        model = FloorPlan


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class DeviceCoordinatesView(ProtectedAPIMixin, generics.RetrieveUpdateAPIView):
    serializer_class = DeviceCoordinatesSerializer
    permission_classes = (DevicePermission,)
    queryset = Device.objects.select_related(
        'devicelocation', 'devicelocation__location'
    )

    def get_queryset(self):
        # It is required to override ProtectedAPIMixin.get_queryset
        # which filters the queryset for organizations managed.
        return self.queryset

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
        if self.request.method == 'PUT':
            return self.create_location(device)
        raise NotFound

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
        self.get_serializer_context()

        return location


class DeviceLocationView(
    ProtectedAPIMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = DeviceLocationSerializer
    queryset = DeviceLocation.objects.select_related(
        'content_object', 'location', 'floorplan', 'content_object__organization'
    )
    lookup_field = 'content_object'
    lookup_url_kwarg = 'pk'
    organization_field = 'content_object__organization'

    def get_queryset(self):
        qs = super().get_queryset()
        try:
            return qs.filter(content_object=self.kwargs['pk'])
        except ValidationError:
            return qs.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({'device_id': self.kwargs['pk']})
        return context

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object_or_none()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if instance is None:
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        self.perform_update(serializer)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def get_object_or_none(self):
        try:
            return self.get_object()
        except Http404:
            if self.request.method == 'PUT':
                # For PUT-as-create operation, we need to ensure that we have
                # relevant permissions, as if this was a POST request. This
                # will either raise a PermissionDenied exception, or simply
                # return None.
                self.check_permissions(clone_request(self.request, 'POST'))
            else:
                # PATCH requests where the object does not exist should still
                # return a 404 response.
                raise


class GeoJsonLocationListPagination(GeoJsonPagination):
    page_size = 1000


class GeoJsonLocationList(
    ProtectedAPIMixin, FilterByOrganizationManaged, generics.ListAPIView
):
    """
    Shows only locations which are assigned to devices.
    """

    queryset = Location.objects.filter(devicelocation__isnull=False).annotate(
        device_count=Count('devicelocation')
    )
    serializer_class = GeoJsonLocationSerializer
    pagination_class = GeoJsonLocationListPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = LocationOrganizationSlugFilter


class LocationDeviceList(
    FilterByParentManaged, ProtectedAPIMixin, generics.ListAPIView
):
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


class FloorPlanListCreateView(ProtectedAPIMixin, generics.ListCreateAPIView):
    serializer_class = FloorPlanSerializer
    queryset = FloorPlan.objects.select_related().order_by('-created')
    pagination_class = ListViewPagination
    filter_backends = [filters.DjangoFilterBackend]
    filter_class = FloorPlanOrganizationSlugFilter


class FloorPlanDetailView(
    ProtectedAPIMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = FloorPlanSerializer
    queryset = FloorPlan.objects.select_related()


class LocationListCreateView(ProtectedAPIMixin, generics.ListCreateAPIView):
    serializer_class = LocationSerializer
    queryset = Location.objects.order_by('-created')
    pagination_class = ListViewPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = LocationOrganizationSlugFilter


class LocationDetailView(
    ProtectedAPIMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = LocationSerializer
    queryset = Location.objects.all()


device_coordinates = DeviceCoordinatesView.as_view()
device_location = DeviceLocationView.as_view()
geojson = GeoJsonLocationList.as_view()
location_device_list = LocationDeviceList.as_view()
list_floorplan = FloorPlanListCreateView.as_view()
detail_floorplan = FloorPlanDetailView.as_view()
list_location = LocationListCreateView.as_view()
detail_location = LocationDetailView.as_view()

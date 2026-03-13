from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Count, Prefetch
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from rest_framework import generics, pagination, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import clone_request
from rest_framework.response import Response
from rest_framework_gis.pagination import GeoJsonPagination
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings
from openwisp_controller.config.api.views import DeviceListCreateView
from openwisp_users.api.filters import OrganizationManagedFilter
from openwisp_users.api.mixins import FilterByOrganizationManaged, FilterByParentManaged

from ...mixins import (
    BaseProtectedAPIMixin,
    ProtectedAPIMixin,
    RelatedDeviceProtectedAPIMixin,
)
from .filters import DeviceListFilter
from .serializers import (
    DeviceCoordinatesSerializer,
    DeviceLocationSerializer,
    FloorPlanSerializer,
    GeoJsonLocationSerializer,
    IndoorCoordinatesSerializer,
    LocationDeviceSerializer,
    LocationSerializer,
)

Device = load_model("config", "Device")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")
FloorPlan = load_model("geo", "FloorPlan")


class DevicePermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        # checks for presence of key attribute first
        # because in the browsable UI this method is
        # getting passed also Location instances,
        # which do not have the key attribute
        return hasattr(obj, "key") and request.query_params.get("key") == obj.key


class LocationOrganizationFilter(OrganizationManagedFilter):
    class Meta(OrganizationManagedFilter.Meta):
        model = Location
        fields = OrganizationManagedFilter.Meta.fields + ["is_mobile", "type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This is evaluated at runtime, which makes it suited
        # For the automated testing strategy we are using.
        # Defining this at class definition does not allow flexible testing.
        if config_app_settings.WHOIS_CONFIGURED:
            self.filters["is_estimated"] = filters.BooleanFilter(
                field_name="is_estimated",
                label=_("Is geographic location estimated?"),
            )


class FloorPlanOrganizationFilter(OrganizationManagedFilter):
    class Meta(OrganizationManagedFilter.Meta):
        model = FloorPlan


class IndoorCoordinatesFilter(filters.FilterSet):
    floor = filters.NumberFilter(label=_("Floor"), method="filter_by_floor")

    @property
    def qs(self):
        qs = super().qs
        if "floor" not in self.data:
            qs = self.filter_by_floor(qs, "floor", None)
        return qs

    def filter_by_floor(self, queryset, name, value):
        """
        If no floor parameter is provided:
        - Return data for the first available non-negative floor.
        - If no non-negative floor exists, return data for the maximum negative floor.
        """
        if value is not None:
            return queryset.filter(floorplan__floor=value)
        # No floor parameter provided
        floors = list(queryset.values_list("floorplan__floor", flat=True).distinct())
        if not floors:
            return queryset.none()
        non_negative_floors = [f for f in floors if f >= 0]
        default_floor = min(non_negative_floors) if non_negative_floors else max(floors)
        return queryset.filter(floorplan__floor=default_floor)

    class Meta(OrganizationManagedFilter.Meta):
        model = DeviceLocation
        fields = ["floor"]


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class DeviceCoordinatesView(ProtectedAPIMixin, generics.RetrieveUpdateAPIView):
    serializer_class = DeviceCoordinatesSerializer
    permission_classes = (DevicePermission,)
    queryset = Device.objects.select_related(
        "devicelocation", "devicelocation__location"
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
        if self.request.method not in ("GET", "HEAD") and device.is_deactivated():
            raise PermissionDenied
        location = self.get_location(device)
        if location:
            return location
        if self.request.method == "PUT":
            return self.create_location(device)
        raise NotFound

    def create_location(self, device):
        location = Location(
            name=device.name,
            type="outdoor",
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
    RelatedDeviceProtectedAPIMixin,
    FilterByParentManaged,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = DeviceLocationSerializer
    queryset = DeviceLocation.objects.select_related(
        "content_object", "location", "floorplan", "content_object__organization"
    )
    lookup_field = "content_object"
    lookup_url_kwarg = "pk"
    organization_field = "content_object__organization"
    organization_lookup = "organization__in"
    _device_field = "content_object"

    def get_queryset(self):
        qs = super().get_queryset()
        try:
            return qs.filter(content_object=self.kwargs["pk"])
        except ValidationError:
            return qs.none()

    def get_parent_queryset(self):
        return Device.objects.filter(pk=self.kwargs["pk"])

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"device_id": self.kwargs["pk"]})
        return context

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
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
            if self.request.method == "PUT":
                # For PUT-as-create operation, we need to ensure that we have
                # relevant permissions, as if this was a POST request. This
                # will either raise a PermissionDenied exception, or simply
                # return None.
                self.check_permissions(clone_request(self.request, "POST"))
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

    queryset = (
        Location.objects.filter(devicelocation__isnull=False)
        .annotate(device_count=Count("devicelocation"))
        .order_by("-created")
    )
    serializer_class = GeoJsonLocationSerializer
    pagination_class = GeoJsonLocationListPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = LocationOrganizationFilter


class IndoorCoordinatesViewPagination(ListViewPagination):
    page_size = 50


class IndoorCoordinatesList(
    FilterByParentManaged, BaseProtectedAPIMixin, generics.ListAPIView
):
    serializer_class = IndoorCoordinatesSerializer
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = IndoorCoordinatesFilter
    pagination_class = IndoorCoordinatesViewPagination
    queryset = (
        DeviceLocation.objects.filter(
            location__type="indoor",
            floorplan__isnull=False,
        )
        .select_related(
            "content_object", "location", "floorplan", "location__organization"
        )
        .order_by("floorplan__floor")
    )

    def get_parent_queryset(self):
        qs = Location.objects.filter(pk=self.kwargs["pk"])
        return qs

    def get_queryset(self):
        return super().get_queryset().filter(location_id=self.kwargs["pk"])

    def get_available_floors(self, qs):
        floors = list(qs.values_list("floorplan__floor", flat=True).distinct())
        return floors

    def list(self, request, *args, **kwargs):
        floors = self.get_available_floors(self.get_queryset())
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            response.data["floors"] = floors
        return response


class LocationDeviceList(
    FilterByParentManaged, ProtectedAPIMixin, generics.ListAPIView
):
    serializer_class = LocationDeviceSerializer
    pagination_class = ListViewPagination
    queryset = Device.objects.none()

    def get_parent_queryset(self):
        qs = Location.objects.filter(pk=self.kwargs["pk"])
        return qs

    def get_queryset(self):
        super().get_queryset()
        qs = Device.objects.filter(devicelocation__location_id=self.kwargs["pk"])
        return qs

    def get_has_floorplan(self, qs):
        qs = qs.filter(devicelocation__floorplan__isnull=False).exists()
        return qs

    def list(self, request, *args, **kwargs):
        has_floorplan = self.get_has_floorplan(self.get_queryset())
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            response.data["has_floorplan"] = has_floorplan
        return response


class FloorPlanListCreateView(ProtectedAPIMixin, generics.ListCreateAPIView):
    serializer_class = FloorPlanSerializer
    queryset = FloorPlan.objects.select_related().order_by("-created")
    pagination_class = ListViewPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = FloorPlanOrganizationFilter


class FloorPlanDetailView(
    ProtectedAPIMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = FloorPlanSerializer
    queryset = FloorPlan.objects.select_related()


class LocationListCreateView(ProtectedAPIMixin, generics.ListCreateAPIView):
    serializer_class = LocationSerializer
    queryset = Location.objects.prefetch_related(
        Prefetch(
            "floorplan_set",
            queryset=FloorPlan.objects.order_by("-created"),
        )
    ).order_by("-created")
    pagination_class = ListViewPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = LocationOrganizationFilter


class LocationDetailView(
    ProtectedAPIMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = LocationSerializer
    queryset = Location.objects.all()


# add with_geo filter to device API
DeviceListCreateView.filterset_class = DeviceListFilter

device_coordinates = DeviceCoordinatesView.as_view()
device_location = DeviceLocationView.as_view()
geojson = GeoJsonLocationList.as_view()
location_device_list = LocationDeviceList.as_view()
list_floorplan = FloorPlanListCreateView.as_view()
detail_floorplan = FloorPlanDetailView.as_view()
indoor_coordinates_list = IndoorCoordinatesList.as_view()
list_location = LocationListCreateView.as_view()
detail_location = LocationDetailView.as_view()

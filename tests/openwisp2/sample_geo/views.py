from openwisp_controller.geo.api.views import (
    DeviceLocationView as BaseDeviceLocationView,
)
from openwisp_controller.geo.api.views import (
    FloorPlanDetailView as BaseFloorPlanDetailView,
)
from openwisp_controller.geo.api.views import (
    FloorPlanListCreateView as BaseFloorPlanListCreateView,
)
from openwisp_controller.geo.api.views import (
    GeoJsonLocationList as BaseGeoJsonLocationList,
)
from openwisp_controller.geo.api.views import (
    LocationDetailView as BaseLocationDetailView,
)
from openwisp_controller.geo.api.views import (
    LocationDeviceList as BaseLocationDeviceList,
)
from openwisp_controller.geo.api.views import (
    LocationListCreateView as BaseLocationListCreateView,
)


class DeviceLocationView(BaseDeviceLocationView):
    pass


class GeoJsonLocationList(BaseGeoJsonLocationList):
    pass


class LocationDeviceList(BaseLocationDeviceList):
    pass


class FloorPlanListCreateView(BaseFloorPlanListCreateView):
    pass


class FloorPlanDetailView(BaseFloorPlanDetailView):
    pass


class LocationListCreateView(BaseLocationListCreateView):
    pass


class LocationDetailView(BaseLocationDetailView):
    pass


device_location = DeviceLocationView.as_view()
geojson = GeoJsonLocationList.as_view()
location_device_list = LocationDeviceList.as_view()
list_floorplan = FloorPlanListCreateView.as_view()
detail_floorplan = FloorPlanDetailView.as_view()
list_location = LocationListCreateView.as_view()
detail_location = LocationDetailView.as_view()

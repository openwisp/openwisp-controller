from openwisp_controller.geo.api.views import (
    DeviceLocationView as BaseDeviceLocationView,
)
from openwisp_controller.geo.api.views import (
    GeoJsonLocationList as BaseGeoJsonLocationList,
)
from openwisp_controller.geo.api.views import (
    LocationDeviceList as BaseLocationDeviceList,
)


class DeviceLocationView(BaseDeviceLocationView):
    pass


class GeoJsonLocationList(BaseGeoJsonLocationList):
    pass


class LocationDeviceList(BaseLocationDeviceList):
    pass


device_location = DeviceLocationView.as_view()
geojson = GeoJsonLocationList.as_view()
location_device_list = LocationDeviceList.as_view()

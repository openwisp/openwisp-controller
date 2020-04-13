from openwisp_controller.geo.api.views import (
    DeviceLocationView as BaseDeviceLocationView,
)


class DeviceLocationView(BaseDeviceLocationView):
    pass


device_location = DeviceLocationView.as_view()

from swapper import load_model

from openwisp_controller.config.controller.views import (
    DeviceChecksumView as BaseDeviceChecksumView,
)
from openwisp_controller.config.controller.views import (
    DeviceDownloadConfigView as BaseDeviceDownloadConfigView,
)
from openwisp_controller.config.controller.views import (
    DeviceRegisterView as BaseDeviceRegisterView,
)
from openwisp_controller.config.controller.views import (
    DeviceReportStatusView as BaseDeviceReportStatusView,
)
from openwisp_controller.config.controller.views import (
    DeviceUpdateInfoView as BaseDeviceUpdateInfoView,
)
from openwisp_controller.config.controller.views import (
    VpnChecksumView as BaseVpnChecksumView,
)
from openwisp_controller.config.controller.views import (
    VpnDownloadConfigView as BaseVpnDownloadConfigView,
)

Device = load_model('config', 'Device')
OrganizationConfigSettings = load_model('config', 'OrganizationConfigSettings')
Vpn = load_model('config', 'Vpn')


class DeviceChecksumView(BaseDeviceChecksumView):
    model = Device


class DeviceDownloadConfigView(BaseDeviceDownloadConfigView):
    model = Device


class DeviceUpdateInfoView(BaseDeviceUpdateInfoView):
    model = Device


class DeviceReportStatusView(BaseDeviceReportStatusView):
    model = Device


class DeviceRegisterView(BaseDeviceRegisterView):
    model = Device
    org_config_settings_model = OrganizationConfigSettings


class VpnChecksumView(BaseVpnChecksumView):
    model = Vpn


class VpnDownloadConfigView(BaseVpnDownloadConfigView):
    model = Vpn


device_checksum = DeviceChecksumView.as_view()
device_download_config = DeviceDownloadConfigView.as_view()
device_update_info = DeviceUpdateInfoView.as_view()
device_report_status = DeviceReportStatusView.as_view()
device_register = DeviceRegisterView.as_view()
vpn_checksum = VpnChecksumView.as_view()
vpn_download_config = VpnDownloadConfigView.as_view()

from openwisp_controller.config.api.views import (
    DeviceDetailView as BaseDeviceDetailView,
)
from openwisp_controller.config.api.views import (
    DeviceListCreateView as BaseDeviceListCreateView,
)
from openwisp_controller.config.api.views import (
    DownloadDeviceView as BaseDownloadDeviceView,
)
from openwisp_controller.config.api.views import (
    DownloadTemplateconfiguration as BaseDownloadTemplateconfiguration,
)
from openwisp_controller.config.api.views import DownloadVpnView as BaseDownloadVpnView
from openwisp_controller.config.api.views import (
    TemplateDetailView as BaseTemplateDetailView,
)
from openwisp_controller.config.api.views import (
    TemplateListCreateView as BaseTemplateListCreateView,
)
from openwisp_controller.config.api.views import VpnDetailView as BaseVpnDetailView
from openwisp_controller.config.api.views import (
    VpnListCreateView as BaseVpnListCreateView,
)


class TemplateListCreateView(BaseTemplateListCreateView):
    pass


class TemplateDetailView(BaseTemplateDetailView):
    pass


class DownloadTemplateconfiguration(BaseDownloadTemplateconfiguration):
    pass


class VpnListCreateView(BaseVpnListCreateView):
    pass


class VpnDetailView(BaseVpnDetailView):
    pass


class DownloadVpnView(BaseDownloadVpnView):
    pass


class DeviceListCreateView(BaseDeviceListCreateView):
    pass


class DeviceDetailView(BaseDeviceDetailView):
    pass


class DownloadDeviceView(BaseDownloadDeviceView):
    pass


template_list = TemplateListCreateView.as_view()
template_detail = TemplateDetailView.as_view()
download_template_config = DownloadTemplateconfiguration.as_view()
vpn_list = VpnListCreateView.as_view()
vpn_detail = VpnDetailView.as_view()
download_vpn_config = DownloadVpnView.as_view()
device_list = DeviceListCreateView.as_view()
device_detail = DeviceDetailView.as_view()
download_device_config = DownloadDeviceView().as_view()

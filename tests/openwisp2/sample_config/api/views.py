from openwisp_controller.config.api.download_views import (
    DownloadDeviceView as BaseDownloadDeviceView,
)
from openwisp_controller.config.api.download_views import (
    DownloadTemplateconfiguration as BaseDownloadTemplateconfiguration,
)
from openwisp_controller.config.api.download_views import (
    DownloadVpnView as BaseDownloadVpnView,
)
from openwisp_controller.config.api.views import (
    DeviceActivateView as BaseDeviceActivateView,
)
from openwisp_controller.config.api.views import (
    DeviceDeactivateView as BaseDeviceDeactivateView,
)
from openwisp_controller.config.api.views import (
    DeviceDetailView as BaseDeviceDetailView,
)
from openwisp_controller.config.api.views import (
    DeviceGroupCommonName as BaseDeviceGroupCommonName,
)
from openwisp_controller.config.api.views import (
    DeviceGroupDetailView as BaseDeviceGroupDetailView,
)
from openwisp_controller.config.api.views import (
    DeviceGroupListCreateView as BaseDeviceGroupListCreateView,
)
from openwisp_controller.config.api.views import (
    DeviceListCreateView as BaseDeviceListCreateView,
)
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


class DeviceActivateView(BaseDeviceActivateView):
    pass


class DeviceDeactivateView(BaseDeviceDeactivateView):
    pass


class DeviceGroupListCreateView(BaseDeviceGroupListCreateView):
    pass


class DeviceGroupDetailView(BaseDeviceGroupDetailView):
    pass


class DeviceGroupCommonName(BaseDeviceGroupCommonName):
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
device_activate = DeviceActivateView.as_view()
device_deactivate = DeviceDeactivateView.as_view()
download_device_config = DownloadDeviceView().as_view()
devicegroup_list = DeviceGroupListCreateView.as_view()
devicegroup_detail = DeviceGroupDetailView.as_view()
devicegroup_commonname = DeviceGroupCommonName.as_view()

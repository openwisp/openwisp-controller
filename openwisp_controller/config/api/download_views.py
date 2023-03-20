# API download views are stored separately from the main API view file
# to avoid import issues when importing the main views from other modules,
# eg: OpenWISP Monitoring. Find out more information at
# https://github.com/openwisp/openwisp-monitoring/pull/480#issuecomment-1475240768

from rest_framework.generics import RetrieveAPIView
from swapper import load_model

from ...mixins import ProtectedAPIMixin
from ..admin import BaseConfigAdmin
from .serializers import DeviceListSerializer, TemplateSerializer, VpnSerializer

Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')
Template = load_model('config', 'Template')


class DownloadVpnView(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = VpnSerializer
    queryset = Vpn.objects.none()
    model = Vpn

    def retrieve(self, request, *args, **kwargs):
        return BaseConfigAdmin.download_view(self, request, pk=kwargs['pk'])


class DownloadDeviceView(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = DeviceListSerializer
    queryset = Device.objects.none()
    model = Device

    def retrieve(self, request, *args, **kwargs):
        return BaseConfigAdmin.download_view(self, request, pk=kwargs['pk'])


class DownloadTemplateconfiguration(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = TemplateSerializer
    queryset = Template.objects.none()
    model = Template

    def retrieve(self, request, *args, **kwargs):
        return BaseConfigAdmin.download_view(self, request, pk=kwargs['pk'])


download_vpn_config = DownloadVpnView.as_view()
download_device_config = DownloadDeviceView().as_view()
download_template_config = DownloadTemplateconfiguration.as_view()

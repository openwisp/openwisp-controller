from rest_framework import pagination
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from swapper import load_model

from openwisp_users.api.authentication import BearerAuthentication
from openwisp_users.api.mixins import FilterByOrganizationManaged

from ..admin import BaseConfigAdmin
from .serializers import (
    DeviceDetailSerializer,
    DeviceListSerializer,
    TemplateSerializer,
    VpnSerializer,
)

Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')
Config = load_model('config', 'Config')


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProtectedAPIMixin(FilterByOrganizationManaged):
    authentication_classes = [BearerAuthentication, SessionAuthentication]
    permission_classes = [
        IsAuthenticated,
        DjangoModelPermissions,
    ]


class TemplateListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    serializer_class = TemplateSerializer
    queryset = Template.objects.order_by('-created')
    pagination_class = ListViewPagination


class TemplateDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = TemplateSerializer
    queryset = Template.objects.all()


class DownloadTemplateconfiguration(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = TemplateSerializer
    queryset = Template.objects.none()
    model = Template

    def retrieve(self, request, *args, **kwargs):
        return BaseConfigAdmin.download_view(self, request, pk=kwargs['pk'])


class VpnListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    serializer_class = VpnSerializer
    queryset = Vpn.objects.order_by('-created')
    pagination_class = ListViewPagination


class VpnDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = VpnSerializer
    queryset = Vpn.objects.all()


class DownloadVpnView(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = VpnSerializer
    queryset = Vpn.objects.none()
    model = Vpn

    def retrieve(self, request, *args, **kwargs):
        return BaseConfigAdmin.download_view(self, request, pk=kwargs['pk'])


class DeviceListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    """
    Templates: Templates flagged as required will be added automatically
               to the `config` of a device and cannot be unassigned.
    """

    serializer_class = DeviceListSerializer
    queryset = Device.objects.select_related('config').order_by('-created')
    pagination_class = ListViewPagination


class DeviceDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    """
    Templates: Templates flagged as _required_ will be added automatically
               to the `config` of a device and cannot be unassigned.
    """

    serializer_class = DeviceDetailSerializer
    queryset = Device.objects.select_related('config')


class DownloadDeviceView(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = DeviceListSerializer
    queryset = Device.objects.none()
    model = Device

    def retrieve(self, request, *args, **kwargs):
        return BaseConfigAdmin.download_view(self, request, pk=kwargs['pk'])


template_list = TemplateListCreateView.as_view()
template_detail = TemplateDetailView.as_view()
download_template_config = DownloadTemplateconfiguration.as_view()
vpn_list = VpnListCreateView.as_view()
vpn_detail = VpnDetailView.as_view()
download_vpn_config = DownloadVpnView.as_view()
device_list = DeviceListCreateView.as_view()
device_detail = DeviceDetailView.as_view()
download_device_config = DownloadDeviceView().as_view()

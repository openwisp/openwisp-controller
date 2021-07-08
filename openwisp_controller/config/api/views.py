from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework import pagination
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAuthenticated
from swapper import load_model

from openwisp_users.api.authentication import BearerAuthentication
from openwisp_users.api.mixins import FilterByOrganizationManaged
from openwisp_users.api.permissions import DjangoModelPermissions

from ..admin import BaseConfigAdmin
from .serializers import (
    DeviceDetailSerializer,
    DeviceGroupSerializer,
    DeviceListSerializer,
    TemplateSerializer,
    VpnSerializer,
)

Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')
DeviceGroup = load_model('config', 'DeviceGroup')
Config = load_model('config', 'Config')
VpnClient = load_model('config', 'VpnClient')
Cert = load_model('django_x509', 'Cert')


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
    queryset = Device.objects.select_related(
        'config', 'group', 'organization'
    ).order_by('-created')
    pagination_class = ListViewPagination


class DeviceDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    """
    Templates: Templates flagged as _required_ will be added automatically
               to the `config` of a device and cannot be unassigned.
    """

    serializer_class = DeviceDetailSerializer
    queryset = Device.objects.select_related('config', 'group', 'organization')


class DownloadDeviceView(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = DeviceListSerializer
    queryset = Device.objects.none()
    model = Device

    def retrieve(self, request, *args, **kwargs):
        return BaseConfigAdmin.download_view(self, request, pk=kwargs['pk'])


class DeviceGroupListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    serializer_class = DeviceGroupSerializer
    queryset = DeviceGroup.objects.select_related('organization').order_by('-created')
    pagination_class = ListViewPagination


class DeviceGroupDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = DeviceGroupSerializer
    queryset = DeviceGroup.objects.select_related('organization').order_by('-created')


# TODO: Think of a better identifier
class DeviceGroupFromCommonName(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = DeviceGroupSerializer
    queryset = DeviceGroup.objects.select_related('organization').order_by('-created')
    # Not setting lookup_field makes DRF raise error. but it is not used
    lookup_field = 'pk'

    def get_object(self):
        org_slugs = self.kwargs['organization_slug'].split(',')
        common_name = self.kwargs['common_name']
        try:
            cert = (
                Cert.objects.select_related('organization')
                .only('id', 'organization')
                .filter(organization__slug__in=org_slugs, common_name=common_name)
                .first()
            )
            vpnclient = VpnClient.objects.only('config_id').get(cert_id=cert.id)
            group = (
                Device.objects.select_related('group')
                .only('group')
                .get(config=vpnclient.config_id)
                .group
            )
            assert group is not None
        except (ObjectDoesNotExist, AssertionError, AttributeError):
            raise Http404
        # May raise a permission denied
        self.check_object_permissions(self.request, group)
        return group


template_list = TemplateListCreateView.as_view()
template_detail = TemplateDetailView.as_view()
download_template_config = DownloadTemplateconfiguration.as_view()
vpn_list = VpnListCreateView.as_view()
vpn_detail = VpnDetailView.as_view()
download_vpn_config = DownloadVpnView.as_view()
device_list = DeviceListCreateView.as_view()
device_detail = DeviceDetailView.as_view()
devicegroup_list = DeviceGroupListCreateView.as_view()
devicegroup_detail = DeviceGroupDetailView.as_view()
devicegroup_from_commonname = DeviceGroupFromCommonName.as_view()
download_device_config = DownloadDeviceView().as_view()

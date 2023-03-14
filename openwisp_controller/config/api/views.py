from cache_memoize import cache_memoize
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F, Q
from django.http import Http404
from django.urls.base import reverse
from django_filters import rest_framework as filters
from rest_framework import pagination
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from swapper import load_model

from ...mixins import ProtectedAPIMixin
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
Organization = load_model('openwisp_users', 'Organization')


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class TemplateListFilter(filters.FilterSet):

    organization = filters.CharFilter(field_name='organization', label='Organization')

    class Meta:
        model = Template
        fields = {
            'organization': ['exact'],
            'backend': ['exact'],
            'type': ['exact'],
            'default': ['exact'],
            'required': ['exact'],
            'created': ['exact', 'gte', 'lt'],
        }


class TemplateListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    serializer_class = TemplateSerializer
    queryset = Template.objects.order_by('-created')
    pagination_class = ListViewPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = TemplateListFilter


class TemplateDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = TemplateSerializer
    queryset = Template.objects.all()


class DownloadTemplateconfiguration(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = TemplateSerializer
    queryset = Template.objects.none()
    model = Template

    def retrieve(self, request, *args, **kwargs):
        return BaseConfigAdmin.download_view(self, request, pk=kwargs['pk'])


class VPNListFilter(filters.FilterSet):

    organization = filters.CharFilter(field_name='organization', label='Organization')
    subnet = filters.CharFilter(field_name='subnet', label='VPN Subnet')

    class Meta:
        model = Vpn
        fields = {
            'backend': ['exact'],
            'subnet': ['exact'],
            'organization': ['exact'],
        }


class VpnListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    serializer_class = VpnSerializer
    queryset = Vpn.objects.select_related('subnet').order_by('-created')
    pagination_class = ListViewPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = VPNListFilter


class VpnDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = VpnSerializer
    queryset = Vpn.objects.all()


class DownloadVpnView(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = VpnSerializer
    queryset = Vpn.objects.none()
    model = Vpn

    def retrieve(self, request, *args, **kwargs):
        return BaseConfigAdmin.download_view(self, request, pk=kwargs['pk'])


class DeviceListFilter(filters.FilterSet):
    config__templates = filters.CharFilter(
        field_name='config__templates', label='Config template'
    )
    organization = filters.CharFilter(field_name='organization', label='Organization')
    group = filters.CharFilter(field_name='group', label='Device group')
    devicelocation = filters.BooleanFilter(
        field_name='devicelocation', method='filter_devicelocation'
    )

    def filter_devicelocation(self, queryset, name, value):
        # Returns list of device that have devicelocation objects
        return queryset.exclude(devicelocation__isnull=value)

    def _set_valid_filterform_lables(self):
        # When not filtering on a model field, an error message
        # with the label "[invalid_name]" will be displayed in filter form.
        # To avoid this error, you need to provide the label explicitly.
        self.filters['config__status'].label = 'Config status'
        self.filters['config__backend'].label = 'Config backend'
        self.filters['devicelocation'].label = 'DeviceLocation'

    def __init__(self, *args, **kwargs):
        super(DeviceListFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_lables()

    class Meta:
        model = Device
        fields = {
            'config__status': ['exact'],
            'config__backend': ['exact'],
            'organization': ['exact'],
            'config__templates': ['exact'],
            'group': ['exact'],
            'devicelocation': ['exact'],
            'created': ['exact', 'gte', 'lt'],
        }


class DeviceListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    """
    Templates: Templates flagged as required will be added automatically
               to the `config` of a device and cannot be unassigned.
    """

    serializer_class = DeviceListSerializer
    queryset = Device.objects.select_related(
        'config', 'group', 'organization', 'devicelocation'
    ).order_by('-created')
    pagination_class = ListViewPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = DeviceListFilter


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


class DeviceGroupListFilter(filters.FilterSet):

    organization = filters.CharFilter(field_name='organization', label='Organization')
    device = filters.BooleanFilter(field_name='device', method='filter_device')

    def filter_device(self, queryset, name, value):
        # Returns list of device groups that have devicelocation objects
        return queryset.exclude(device__isnull=value).distinct()

    def _set_valid_filterform_lables(self):
        # When not filtering on a model field, an error message
        # with the label "[invalid_name]" will be displayed in filter form.
        # To avoid this error, you need to provide the label explicitly.
        self.filters['device'].label = 'Has devices'

    def __init__(self, *args, **kwargs):
        super(DeviceGroupListFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_lables()

    class Meta:
        model = DeviceGroup
        fields = {
            'organization': ['exact'],
            'device': ['exact'],
        }


class DeviceGroupListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    serializer_class = DeviceGroupSerializer
    queryset = DeviceGroup.objects.prefetch_related('templates').order_by('-created')
    pagination_class = ListViewPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = DeviceGroupListFilter


class DeviceGroupDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = DeviceGroupSerializer
    queryset = DeviceGroup.objects.select_related('organization').order_by('-created')


def get_cached_devicegroup_args_rewrite(cls, org_slugs, common_name):
    url = reverse(
        'config_api:devicegroup_x509_commonname',
        args=[common_name],
    )
    url = f'{url}?org={org_slugs}'
    return url


class DeviceGroupCommonName(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = DeviceGroupSerializer
    queryset = DeviceGroup.objects.select_related('organization').order_by('-created')
    # Not setting lookup_field makes DRF raise error. but it is not used
    lookup_field = 'pk'

    @classmethod
    @cache_memoize(
        timeout=24 * 60 * 60, args_rewrite=get_cached_devicegroup_args_rewrite
    )
    def get_device_group(cls, org_slugs, common_name):
        query = Q(common_name=common_name)
        if org_slugs:
            org_slugs = org_slugs.split(',')
            query = query & Q(organization__slug__in=org_slugs)
        try:
            cert = (
                Cert.objects.select_related('organization')
                .only('id', 'organization')
                .filter(query)
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
        return group

    def get_object(self):
        org_slugs = self.request.query_params.get('org', '')
        common_name = self.kwargs['common_name']
        group = self.get_device_group(org_slugs, common_name)
        # May raise a permission denied
        self.check_object_permissions(self.request, group)
        return group

    @classmethod
    def _invalidate_from_queryset(cls, queryset):
        for obj in queryset.iterator():
            if not obj['common_name']:
                return
            cls.get_device_group.invalidate(None, '', obj['common_name'])
            cls.get_device_group.invalidate(
                None, obj['organization__slug'], obj['common_name']
            )

    @classmethod
    def device_change_invalidates_cache(cls, device_id):
        qs = (
            VpnClient.objects.select_related(
                'config',
                'organization',
                'cert',
            )
            .filter(config__device_id=device_id)
            .annotate(
                organization__slug=F('cert__organization__slug'),
                common_name=F('cert__common_name'),
            )
            .values('common_name', 'organization__slug')
        )
        cls._invalidate_from_queryset(qs)

    @classmethod
    def devicegroup_change_invalidates_cache(cls, device_group_id):
        qs = (
            VpnClient.objects.select_related(
                'config',
                'config__device',
                'config__device__group',
                'organization',
                'cert',
            )
            .filter(config__device__group_id=device_group_id)
            .annotate(
                organization__slug=F('cert__organization__slug'),
                common_name=F('cert__common_name'),
            )
            .values('common_name', 'organization__slug')
        )
        cls._invalidate_from_queryset(qs)

    @classmethod
    def certificate_change_invalidates_cache(cls, cert_id):
        qs = (
            Cert.objects.select_related('organization')
            .filter(id=cert_id)
            .values('organization__slug', 'common_name')
        )
        cls._invalidate_from_queryset(qs)

    @classmethod
    def devicegroup_delete_invalidates_cache(cls, organization_id):
        qs = (
            Cert.objects.select_related('organization')
            .filter(organization_id=organization_id)
            .values('organization__slug', 'common_name')
        )
        cls._invalidate_from_queryset(qs)

    @classmethod
    def certificate_delete_invalidates_cache(cls, organization_id, common_name):
        try:
            assert common_name
            org_slug = Organization.objects.only('slug').get(id=organization_id).slug
        except (AssertionError, Organization.DoesNotExist):
            return
        cls.get_device_group.invalidate(cls, '', common_name)
        cls.get_device_group.invalidate(cls, org_slug, common_name)


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
devicegroup_commonname = DeviceGroupCommonName.as_view()
download_device_config = DownloadDeviceView().as_view()

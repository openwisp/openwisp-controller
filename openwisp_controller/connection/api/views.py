from django.core.exceptions import ValidationError
from rest_framework import pagination
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
    get_object_or_404,
)
from swapper import load_model

from openwisp_users.api.authentication import BearerAuthentication

from ...mixins import ProtectedAPIMixin
from .serializer import (
    CommandSerializer,
    CredentialSerializer,
    DeviceConnectionSerializer,
)

Command = load_model('connection', 'Command')
Device = load_model('config', 'Device')
Credentials = load_model('connection', 'Credentials')
DeviceConnection = load_model('connection', 'DeviceConnection')


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class BaseCommandView(GenericAPIView):
    model = Command
    serializer_class = CommandSerializer
    authentication_classes = [BearerAuthentication, SessionAuthentication]

    def get_queryset(self):
        qs = Command.objects.prefetch_related('device')
        if not self.request.user.is_superuser:
            qs = qs.filter(
                device__organization__in=self.request.user.organizations_managed
            )
        return qs

    def initial(self, *args, **kwargs):
        super().initial(*args, **kwargs)
        self.assert_parent_exists()

    def assert_parent_exists(self):
        try:
            assert self.get_parent_queryset().exists()
        except (AssertionError, ValidationError):
            device_id = self.kwargs['id']
            raise NotFound(detail=f'Device with ID "{device_id}" not found.')

    def get_parent_queryset(self):
        return Device.objects.filter(pk=self.kwargs['id'])


class CommandListCreateView(BaseCommandView, ListCreateAPIView):
    pagination_class = ListViewPagination

    def get_queryset(self):
        return super().get_queryset().filter(device_id=self.kwargs['id'])

    def perform_create(self, serializer):
        serializer.save(device_id=self.kwargs['id'])


class CommandDetailsView(BaseCommandView, RetrieveAPIView):
    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {
            'id': self.kwargs['command_id'],
        }
        obj = get_object_or_404(queryset, **filter_kwargs)
        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        return obj


class CredentialListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    queryset = Credentials.objects.order_by('-created')
    serializer_class = CredentialSerializer
    pagination_class = ListViewPagination


class CredentialDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    queryset = Credentials.objects.all()
    serializer_class = CredentialSerializer


class BaseDeviceConection(ProtectedAPIMixin, GenericAPIView):
    model = DeviceConnection
    serializer_class = DeviceConnectionSerializer

    def get_queryset(self):
        return DeviceConnection.objects.prefetch_related('device')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['device_id'] = self.kwargs['pk']
        return context

    def initial(self, *args, **kwargs):
        super().initial(*args, **kwargs)
        self.assert_parent_exists()

    def assert_parent_exists(self):
        try:
            assert self.get_parent_queryset().exists()
        except (AssertionError, ValidationError):
            device_id = self.kwargs['pk']
            raise NotFound(detail=f'Device with ID "{device_id}" not found.')

    def get_parent_queryset(self):
        return Device.objects.filter(pk=self.kwargs['pk'])


class DeviceConnenctionListCreateView(BaseDeviceConection, ListCreateAPIView):
    pagination_class = ListViewPagination

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(device_id=self.kwargs['pk'])
            .order_by('-created')
        )


class DeviceConnectionDetailView(BaseDeviceConection, RetrieveUpdateDestroyAPIView):
    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {
            'id': self.kwargs['connection_id'],
        }
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj


command_list_create_view = CommandListCreateView.as_view()
command_details_view = CommandDetailsView.as_view()
credential_list_create_view = CredentialListCreateView.as_view()
credential_detail_view = CredentialDetailView.as_view()
deviceconnection_list_create_view = DeviceConnenctionListCreateView.as_view()
deviceconnection_details_view = DeviceConnectionDetailView.as_view()

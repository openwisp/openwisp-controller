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
from rest_framework.permissions import IsAuthenticated
from swapper import load_model

from openwisp_users.api.authentication import BearerAuthentication
from openwisp_users.api.mixins import FilterByOrganizationManaged
from openwisp_users.api.permissions import DjangoModelPermissions

from .serializer import CommandSerializer, CredentialSerializer

Command = load_model('connection', 'Command')
Device = load_model('config', 'Device')
Credentials = load_model('connection', 'Credentials')


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


class ProtectedAPIMixin(FilterByOrganizationManaged):
    authentication_classes = [BearerAuthentication, SessionAuthentication]
    permission_classes = [
        IsAuthenticated,
        DjangoModelPermissions,
    ]


class CredentialListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    queryset = Credentials.objects.order_by('-created')
    serializer_class = CredentialSerializer
    pagination_class = ListViewPagination


class CredentialDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    queryset = Credentials.objects.all()
    serializer_class = CredentialSerializer


command_list_create_view = CommandListCreateView.as_view()
command_details_view = CommandDetailsView.as_view()
credential_list_create_view = CredentialListCreateView.as_view()
credential_detail_view = CredentialDetailView.as_view()

from django.core.exceptions import ValidationError
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    get_object_or_404,
)
from rest_framework.pagination import PageNumberPagination
from swapper import load_model

from openwisp_users.api.authentication import BearerAuthentication

from .serializer import CommandSerializer

Command = load_model('connection', 'Command')
Device = load_model('config', 'Device')


class CommandPaginator(PageNumberPagination):
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
            device_pk = self.kwargs['device_pk']
            raise NotFound(detail=f'Device with ID "{device_pk}" not found.')

    def get_parent_queryset(self):
        return Device.objects.filter(pk=self.kwargs['device_pk'])


class CommandListCreateView(BaseCommandView, ListCreateAPIView):
    pagination_class = CommandPaginator

    def get_queryset(self):
        return super().get_queryset().filter(device_id=self.kwargs['device_pk'])

    def perform_create(self, serializer):
        serializer.save(device_id=self.kwargs['device_pk'])


class CommandDetailsView(BaseCommandView, RetrieveAPIView):
    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {
            'id': self.kwargs['command_pk'],
        }
        obj = get_object_or_404(queryset, **filter_kwargs)
        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        return obj


command_list_create_view = CommandListCreateView.as_view()
command_details_view = CommandDetailsView.as_view()

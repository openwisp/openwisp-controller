from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
    get_object_or_404,
)
from rest_framework.response import Response
from swapper import load_model

from openwisp_utils.api.pagination import OpenWispPagination

from ...mixins import (
    ProtectedAPIMixin,
    RelatedDeviceModelPermission,
    RelatedDeviceProtectedAPIMixin,
)
from .serializers import (
    BatchCommandExecuteSerializer,
    CommandSerializer,
    CredentialSerializer,
    DeviceConnectionSerializer,
)

Command = load_model("connection", "Command")
Device = load_model("config", "Device")
Credentials = load_model("connection", "Credentials")
DeviceConnection = load_model("connection", "DeviceConnection")
BatchCommand = load_model("connection", "BatchCommand")


class BaseCommandView(RelatedDeviceProtectedAPIMixin):
    organization_field = "device__organization"
    organization_lookup = "organization__in"
    model = Command
    queryset = Command.objects.prefetch_related("device")
    serializer_class = CommandSerializer

    def get_permissions(self):
        return super().get_permissions() + [RelatedDeviceModelPermission()]

    def get_parent_queryset(self):
        return Device.objects.filter(
            pk=self.kwargs["device_id"],
        )

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(device_id=self.kwargs["device_id"])
            .order_by("-created")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["device_id"] = self.kwargs["device_id"]
        return context


class CommandListCreateView(BaseCommandView, ListCreateAPIView):
    pagination_class = OpenWispPagination

    def create(self, request, *args, **kwargs):
        self.assert_parent_exists()
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description=_("Execute a command on a device"),
        operation_summary=_("Execute device command"),
        request_body=CommandSerializer,
        responses={
            201: openapi.Response(
                description=_("Command created successfully"),
                schema=CommandSerializer,
            ),
            400: openapi.Response(description=_("Invalid request data")),
            404: openapi.Response(description=_("Device not found")),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CommandDetailsView(BaseCommandView, RetrieveAPIView):
    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {
            "id": self.kwargs["pk"],
        }
        obj = get_object_or_404(queryset, **filter_kwargs)
        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        return obj


class CredentialListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    queryset = Credentials.objects.order_by("-created")
    serializer_class = CredentialSerializer
    pagination_class = OpenWispPagination


class CredentialDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    queryset = Credentials.objects.all()
    serializer_class = CredentialSerializer


class BaseDeviceConnection(
    RelatedDeviceProtectedAPIMixin,
):
    organization_field = "device__organization"
    organization_lookup = "organization__in"
    model = DeviceConnection
    serializer_class = DeviceConnectionSerializer
    queryset = DeviceConnection.objects.prefetch_related("device")

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(device_id=self.kwargs["device_id"])
            .order_by("-created")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["device_id"] = self.kwargs["device_id"]
        return context

    def get_parent_queryset(self):
        return Device.objects.filter(pk=self.kwargs["device_id"])


class DeviceConnectionListCreateView(BaseDeviceConnection, ListCreateAPIView):
    pagination_class = OpenWispPagination


# TODO: remove in version 1.4
DeviceConnenctionListCreateView = DeviceConnectionListCreateView


class BatchCommandExecuteView(ProtectedAPIMixin, GenericAPIView):
    model = BatchCommand
    queryset = BatchCommand.objects.all()
    serializer_class = BatchCommandExecuteSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            batch = BatchCommand.execute(**serializer.validated_data)
        except ValidationError as e:
            return Response(
                {"error": str(e.messages[0])}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response({"batch": str(batch.pk)}, status=201)

    def get(self, request):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            data = BatchCommand.dry_run(**serializer.validated_data)
        except ValidationError as e:
            return Response(
                {"error": str(e.messages[0])}, status=status.HTTP_400_BAD_REQUEST
            )
        data["devices"] = [str(d.pk) for d in data["devices"]]
        return Response(data)


class DeviceConnectionDetailView(BaseDeviceConnection, RetrieveUpdateDestroyAPIView):
    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {
            "id": self.kwargs["pk"],
        }
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj


command_list_create_view = CommandListCreateView.as_view()
command_details_view = CommandDetailsView.as_view()
credential_list_create_view = CredentialListCreateView.as_view()
credential_detail_view = CredentialDetailView.as_view()
deviceconnection_list_create_view = DeviceConnectionListCreateView.as_view()
deviceconnection_detail_view = DeviceConnectionDetailView.as_view()

# TODO: remove in version 1.4
deviceconnection_details_view = deviceconnection_detail_view

batch_command_execute_view = BatchCommandExecuteView.as_view()

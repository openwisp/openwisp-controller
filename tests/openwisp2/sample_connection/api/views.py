from openwisp_controller.connection.api.views import (
    CommandDetailsView as BaseCommandDetailsView,
)
from openwisp_controller.connection.api.views import (
    CommandListCreateView as BaseCommandListCreateView,
)
from openwisp_controller.connection.api.views import (
    CredentialDetailView as BaseCredentialDetailView,
)
from openwisp_controller.connection.api.views import (
    CredentialListCreateView as BaseCredentialListCreateView,
)
from openwisp_controller.connection.api.views import (
    DeviceConnectionDetailView as BaseDeviceConnectionDetailView,
)
from openwisp_controller.connection.api.views import (
    DeviceConnenctionListCreateView as BaseDeviceConnenctionListCreateView,
)


class CommandDetailsView(BaseCommandDetailsView):
    pass


class CommandListCreateView(BaseCommandListCreateView):
    pass


class CredentialListCreateView(BaseCredentialListCreateView):
    pass


class CredentialDetailView(BaseCredentialDetailView):
    pass


class DeviceConnenctionListCreateView(BaseDeviceConnenctionListCreateView):
    pass


class DeviceConnectionDetailView(BaseDeviceConnectionDetailView):
    pass


command_list_create_view = CommandListCreateView.as_view()
command_details_view = CommandDetailsView.as_view()
credential_list_create_view = CredentialListCreateView.as_view()
credential_detail_view = CredentialDetailView.as_view()
deviceconnection_list_create_view = DeviceConnenctionListCreateView.as_view()
deviceconnection_details_view = DeviceConnectionDetailView.as_view()

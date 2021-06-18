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


class CommandDetailsView(BaseCommandDetailsView):
    pass


class CommandListCreateView(BaseCommandListCreateView):
    pass


class CredentialListCreateView(BaseCredentialListCreateView):
    pass


class CredentialDetailView(BaseCredentialDetailView):
    pass


command_list_create_view = CommandListCreateView.as_view()
command_details_view = CommandDetailsView.as_view()
credential_list_create_view = CredentialListCreateView.as_view()
credential_detail_view = CredentialDetailView.as_view()

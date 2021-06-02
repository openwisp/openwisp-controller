from openwisp_controller.connection.api.views import (
    CommandDetailsView as BaseCommandDetailsView,
)
from openwisp_controller.connection.api.views import (
    CommandListCreateView as BaseCommandListCreateView,
)


class CommandDetailsView(BaseCommandDetailsView):
    pass


class CommandListCreateView(BaseCommandListCreateView):
    pass


command_list_create_view = CommandListCreateView.as_view()
command_details_view = CommandDetailsView.as_view()

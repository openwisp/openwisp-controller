import json
from copy import deepcopy

from swapper import load_model

from ...config.base.channels_consumer import BaseDeviceConsumer
from .. import settings as app_settings

Device = load_model("config", "Device")
BatchCommand = load_model("connection", "BatchCommand")


class CommandConsumer(BaseDeviceConsumer):
    def send_update(self, event):
        data = deepcopy(event)
        data.pop("type")
        self.send(json.dumps(data))


class BatchCommandConsumer(BaseDeviceConsumer):
    model = BatchCommand
    channel_layer_group = "config.batchcommand"

    def connect(self):
        # ensure the user can only access the batch command if they
        # can view the organization it belongs to
        pk = self.scope["url_route"]["kwargs"]["pk"]
        user = self.scope["user"]
        batch = (
            BatchCommand.objects.select_related("organization").filter(pk=pk).first()
        )
        if not batch:
            self.close()
            return
        if not user.is_superuser and not (
            batch.organization_id
            and user.organizations_managed.filter(pk=batch.organization_id).exists()
        ):
            self.close()
            return
        super().connect()

    def send_update(self, event):
        data = deepcopy(event)
        data.pop("type")
        self.send(json.dumps(data))

    per_page = app_settings.BATCH_COMMAND_PAGE_SIZE

    def receive(self, text_data):
        try:
            content = json.loads(text_data)
        except ValueError:
            return
        if content.get("type") == "request_current_state":
            self._handle_current_state_request(content.get("page"))

    def _handle_current_state_request(self, page=None):
        """Reply with the state of the page the client is showing.

        The client requests this once on websocket open (and on every
        reconnect) so the table can be reconciled even for commands created
        while the page was closed or before the socket connected.

        Only the requested page is sent: a mass command can target thousands
        of devices, and serializing all of them (including their output) on
        every connect would make the payload grow without bound.
        """
        # Imported here instead of at module import time to avoid
        # AppRegistryNotReady errors.
        from ..api.serializers import BatchCommandSerializer, command_to_batch_payload

        batch = BatchCommand.objects.filter(
            pk=self.scope["url_route"]["kwargs"]["pk"]
        ).first()
        if not batch:
            return
        affected_devices = batch.batch_commands.count()
        batch_data = BatchCommandSerializer(batch).data
        batch_data["status_display"] = batch.get_status_display()
        batch_data["affected_devices"] = affected_devices
        try:
            page = max(int(page), 1)
        except (TypeError, ValueError):
            page = 1
        start = (page - 1) * self.per_page
        end = start + self.per_page
        page_commands = batch.batch_commands.select_related("device")[start:end]
        commands = [command_to_batch_payload(command) for command in page_commands]
        self.send(
            json.dumps(
                {
                    "model": "BatchState",
                    "data": {
                        "batch_status": batch_data,
                        "commands": commands,
                        "page": page,
                        # the table paginates the skipped devices too, they
                        # are not Command rows
                        "total_rows": affected_devices
                        + len(batch.skipped_devices or {}),
                    },
                }
            )
        )

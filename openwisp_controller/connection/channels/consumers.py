import json
import logging
from copy import deepcopy

from django.utils.formats import date_format
from django.utils.timezone import localtime
from swapper import load_model

from ...config.base.channels_consumer import BaseDeviceConsumer
from ..api.serializers import BatchCommandSerializer, CommandSerializer

logger = logging.getLogger(__name__)

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
    per_page = 20
    current_state_message = "request_current_state"

    def send_update(self, event):
        self.send(json.dumps(event["data"]))

    def is_user_authorized(self):
        user = self.scope["user"]
        if user.is_superuser:
            return True
        # a mass command cannot be changed or deleted from the admin
        if not (
            user.is_staff and self._user_has_permissions(change=False, delete=False)
        ):
            return False
        organization_id = (
            self.model.objects.filter(pk=self.scope["url_route"]["kwargs"]["pk"])
            .values_list("organization_id", flat=True)
            .first()
        )
        return bool(organization_id) and user.is_manager(str(organization_id))

    def receive(self, text_data):
        try:
            content = json.loads(text_data)
        except ValueError:
            logger.warning("Received a websocket message which is not valid JSON")
            return
        message_type = content.get("type")
        if message_type == self.current_state_message:
            self._handle_current_state_request(content.get("page"))
        else:
            logger.warning(f"Unknown websocket message type received: {message_type}")

    def _handle_current_state_request(self, page=None):
        """Handle request for current state of the operation"""

        batch = BatchCommand.objects.filter(
            pk=self.scope["url_route"]["kwargs"]["pk"]
        ).first()
        if not batch:
            # deleted after the connection was accepted
            return
        batch_status = BatchCommandSerializer(batch).data
        batch_status["status_display"] = batch.get_status_display()
        batch_status["affected_devices"] = batch.affected_devices
        try:
            page = max(int(page), 1)
        except (TypeError, ValueError):
            page = 1
        start = (page - 1) * self.per_page
        end = start + self.per_page
        page_commands = batch.batch_commands.select_related("device")[start:end]
        commands = []
        for command in page_commands:
            row = CommandSerializer(command).data
            row["device_name"] = command.device.name
            row["status_display"] = command.get_status_display()
            row["output"] = command.output_preview
            row["modified"] = date_format(
                localtime(command.modified), "DATETIME_FORMAT"
            )
            commands.append(row)
        self.send(
            json.dumps(
                {
                    "type": "batch_state",
                    "batch_status": batch_status,
                    "commands": commands,
                    "total_rows": batch.total_devices,
                }
            )
        )

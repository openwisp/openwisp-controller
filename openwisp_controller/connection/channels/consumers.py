import json
import logging
from copy import deepcopy

from django.contrib.auth import get_user_model
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

    def _has_access(self):
        """The connected user is reloaded because permissions and organization
        memberships cached on the instance stored in the scope do not reflect
        the changes made after the socket was accepted.
        """
        user = get_user_model().objects.filter(pk=self.scope["user"].pk).first()
        if user is None or not user.is_active:
            return False
        self.scope["user"] = user
        return self.is_user_authorized()

    def send_update(self, event):
        if not self._has_access():
            self.close()
            return
        self.send(json.dumps(event["data"]))

    def is_user_authorized(self):
        user = self.scope["user"]
        if user.is_superuser:
            return True
        opts = self.model._meta
        if not user.is_staff or not any(
            user.has_perm(f"{opts.app_label}.{action}_{opts.model_name}")
            for action in ("view", "change")
        ):
            return False
        organization_id = (
            self.model.objects.filter(pk=self.scope["url_route"]["kwargs"]["pk"])
            .values_list("organization_id", flat=True)
            .first()
        )
        return bool(organization_id) and user.is_manager(str(organization_id))

    def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            logger.warning("Received a binary websocket message, ignoring it")
            return
        try:
            content = json.loads(text_data)
        except ValueError:
            content = None
        if not isinstance(content, dict):
            logger.warning(
                "Received a websocket message which is not a valid JSON object"
            )
            return
        if not self._has_access():
            self.close()
            return
        message_type = content.get("type")
        if message_type == self.current_state_message:
            self._handle_current_state_request(
                content.get("page"), content.get("filters")
            )
        else:
            logger.warning(f"Unknown websocket message type received: {message_type}")

    def _handle_current_state_request(self, page=None, filters=None):
        """Handle request for current state of the operation.

        The page is built from the same filters the browser is showing, so a
        reconnect on a filtered page reconciles against a comparable snapshot
        instead of the whole batch.
        """
        batch = BatchCommand.objects.filter(
            pk=self.scope["url_route"]["kwargs"]["pk"]
        ).first()
        if not batch:
            # deleted after the connection was accepted
            return
        filters = BatchCommand.normalize_filters(filters)
        batch_status = BatchCommandSerializer(batch).data
        batch_status["affected_devices"] = batch.affected_devices
        batch_status.pop("skipped_devices", None)
        batch_status["skipped_count"] = batch.skipped_count
        batch_status["skipped_preview"] = batch.get_skipped_preview()
        commands_qs = batch.filter_commands(
            batch.batch_commands.select_related("device"), filters
        )
        commands_count = commands_qs.count()
        skipped_items = []
        if batch.skipped_count and filters["status"] in ("", "skipped"):
            skipped_items = batch.filter_skipped_items(filters)
        try:
            page = max(int(page), 1)
        except (TypeError, ValueError):
            page = 1
        start = (page - 1) * self.per_page
        end = start + self.per_page
        commands = []
        commands_end = min(end, commands_count)
        for command in commands_qs[start:commands_end]:
            row = CommandSerializer(command).data
            row.pop("input", None)
            row["device_name"] = command.device.name
            row["output"] = command.output_preview
            commands.append(row)
        commands += batch.get_skipped_rows(
            max(0, start - commands_count),
            max(0, end - commands_count),
            items=skipped_items,
        )
        self.send(
            json.dumps(
                {
                    "type": "batch_state",
                    "batch_status": batch_status,
                    "commands": commands,
                    "total_rows": commands_count + len(skipped_items),
                }
            )
        )

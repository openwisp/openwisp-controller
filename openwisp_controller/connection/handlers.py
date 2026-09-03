import logging

from asgiref.sync import async_to_sync
from channels import layers
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from swapper import load_model

logger = logging.getLogger(__name__)

Command = load_model("connection", "Command")
BatchCommand = load_model("connection", "BatchCommand")


def send_update(group, event):
    def send():
        try:
            async_to_sync(layers.get_channel_layer().group_send)(group, event)
        except Exception:
            logger.exception("Failed to send update to %s", group)

    transaction.on_commit(send)


def send_batch_update(group, data):
    send_update(group, {"type": "send.update", "data": data})


@receiver(post_save, sender=Command, dispatch_uid="command_save_handler")
def command_save_handler(sender, created, instance, **kwargs):
    from .api.serializers import CommandSerializer

    if created and not instance.batch_command_id:
        return
    serialized_data = CommandSerializer(instance).data
    if not created:
        send_update(
            f"config.device-{instance.device_id}",
            {"type": "send.update", "model": "Command", "data": serialized_data},
        )
    if instance.batch_command_id:
        batch_data = dict(serialized_data)
        batch_data.pop("input", None)
        batch_data["device_name"] = instance.device.name
        batch_data["output"] = instance.output_preview
        batch_data["type"] = "command_update"
        if created:
            batch = instance.batch_command
            index = getattr(instance, "_batch_index", None)
            if index is None:
                index = batch.affected_devices - 1
            affected_devices = index + 1
            batch_data["index"] = index
            batch_data["affected_devices"] = affected_devices
            batch_data["total_rows"] = affected_devices + batch.skipped_count
        send_batch_update(
            f"config.batchcommand-{instance.batch_command_id}", batch_data
        )


@receiver(post_save, sender=BatchCommand, dispatch_uid="batch_command_save_handler")
def batch_command_save_handler(sender, instance, **kwargs):
    from .api.serializers import BatchCommandSerializer

    batch_data = BatchCommandSerializer(instance).data
    batch_data["type"] = "batch_status"
    affected_devices = instance.affected_devices
    batch_data.pop("skipped_devices", None)
    skipped_count = instance.skipped_count
    batch_data["affected_devices"] = affected_devices
    batch_data["total_rows"] = affected_devices + skipped_count
    batch_data["skipped_count"] = skipped_count
    batch_data["skipped_preview"] = instance.get_skipped_preview()
    send_batch_update(f"config.batchcommand-{instance.pk}", batch_data)

import json

import channels.layers
from asgiref.sync import async_to_sync
from django.db.models.signals import post_save
from django.dispatch import receiver


def update_mobile_location(sender, instance, **kwargs):
    """
    Sends WebSocket updates when a location record is updated.
    - Sends a message to the location specific group.
    - Sends a message to a common group for tracking all mobile location updates.
    """
    if not kwargs.get("created") and instance.geometry:
        channel_layer = channels.layers.get_channel_layer()

        # Send update to location specific group
        async_to_sync(channel_layer.group_send)(
            f"loci.mobile-location.{instance.pk}",
            {
                "type": "send_message",
                "message": {
                    "geometry": json.loads(instance.geometry.geojson),
                    "address": instance.address,
                },
            },
        )

        # Send update to common mobile location group
        async_to_sync(channel_layer.group_send)(
            "loci.mobile-location.common",
            {
                "type": "send_message",
                "message": {
                    "id": str(instance.pk),
                    "geometry": json.loads(instance.geometry.geojson),
                    "address": instance.address,
                    "name": instance.name,
                    "type": instance.type,
                    "is_mobile": instance.is_mobile,
                },
            },
        )


def load_location_receivers(sender):
    """
    enables signal listening when called
    designed to be called in AppConfig subclasses
    """
    # using decorator pattern with old syntax
    # in order to decorate an existing function
    receiver(post_save, sender=sender, dispatch_uid="ws_update_mobile_location")(
        update_mobile_location
    )

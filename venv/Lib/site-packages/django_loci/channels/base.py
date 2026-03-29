from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.core.exceptions import ValidationError

location_broadcast_path = "ws/loci/location/<uuid:pk>/"
common_location_broadcast_path = "ws/loci/location/"


def _get_object_or_none(model, **kwargs):
    try:
        return model.objects.get(**kwargs)
    except (ValidationError, model.DoesNotExist):
        return None


class BaseLocationBroadcast(JsonWebsocketConsumer):
    """
    Base WebSocket consumer for broadcasting location coordinate changes
    to authorized users (superusers or organization operators).
    """

    def connect(self):
        """
        Handle WebSocket connection: authenticate user, validate location,
        and join the location-specific broadcast group.
        """
        self.pk = None
        try:
            user = self.scope["user"]
            self.pk = self.scope["url_route"]["kwargs"]["pk"]
        except KeyError:
            # Will fall here when the scope does not have
            # one of the variables, most commonly, user
            # (When a user tries to access without loggin in)
            self.close()
        else:
            location = _get_object_or_none(self.model, pk=self.pk)
            if not location or not self.is_authorized(user, location):
                self.close()
                return
            self.accept()
            # Create group name once
            self.group_name = "loci.mobile-location.{}".format(self.pk)
            async_to_sync(self.channel_layer.group_add)(
                self.group_name, self.channel_name
            )

    def is_authorized(self, user, location):
        """
        Check if the user has permission to receive location broadcasts.
        Requires authentication and change or view permissions on the location.
        """
        perm = "{0}.change_location".format(self.model._meta.app_label)
        # allow users with view permission
        readperm = "{0}.view_location".format(self.model._meta.app_label)
        authenticated = user.is_authenticated
        is_permitted = user.has_perm(perm) or user.has_perm(readperm)
        return authenticated and (user.is_superuser or (user.is_staff and is_permitted))

    def send_message(self, event):
        """
        Send JSON event data to the connected WebSocket client.
        """
        self.send_json(event["message"])

    def disconnect(self, close_code):
        """
        Handle cleanup on WebSocket disconnection.
        """
        # The group_name is set only when the connection is accepted.
        # Remove the user from the group, if it exists.
        if hasattr(self, "group_name"):
            async_to_sync(self.channel_layer.group_discard)(
                self.group_name, self.channel_name
            )


class BaseCommonLocationBroadcast(BaseLocationBroadcast):

    def connect(self):
        """
        Override connect to handle subscription to all locations
        without requiring a specific location PK.
        """
        try:
            user = self.scope["user"]
        except KeyError:
            self.close()
        else:
            if not self.is_authorized(user, None):
                self.close()
                return
            self.accept()
            self.join_groups(user)

    def join_groups(self, user):
        """
        Subscribe to broadcast groups.
        Subclasses can override to add user-specific groups (using the ``user`` argument).
        """
        self.group_name = "loci.mobile-location.common"
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)

import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import now, timedelta

from openwisp_notifications.api.serializers import IgnoreObjectNotificationSerializer
from openwisp_notifications.swapper import load_model

from .. import settings as app_settings

Notification = load_model("Notification")
IgnoreObjectNotification = load_model("IgnoreObjectNotification")


class NotificationConsumer(WebsocketConsumer):
    _initial_backoff = app_settings.NOTIFICATION_STORM_PREVENTION["initial_backoff"]
    _backoff_increment = app_settings.NOTIFICATION_STORM_PREVENTION["backoff_increment"]
    _max_allowed_backoff = app_settings.NOTIFICATION_STORM_PREVENTION[
        "max_allowed_backoff"
    ]

    def _is_user_authenticated(self):
        try:
            assert self.scope["user"].is_authenticated is True
        except (KeyError, AssertionError):
            self.close()
            return False
        else:
            return True

    def connect(self):
        if self._is_user_authenticated():
            async_to_sync(self.channel_layer.group_add)(
                "ow-notification-{0}".format(self.scope["user"].pk), self.channel_name
            )
            self.accept()
            self.scope["last_update_datetime"] = now()
            self.scope["backoff"] = self._initial_backoff

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            "ow-notification-{0}".format(self.scope["user"].pk), self.channel_name
        )

    def process_event_for_notification_storm(self, event):
        if not event["in_notification_storm"]:
            return event
        # Removing notification is required to prevent frontend
        # from showing toasts.
        event["notification"] = None
        datetime_now = now()
        # If delay exceeds max_allowed_backoff, reset and send
        # update. This is required to trigger reloading of
        # notification widget.
        if (
            self.scope["last_update_datetime"] > datetime_now
            and (self.scope["last_update_datetime"] - datetime_now).seconds
            >= self._max_allowed_backoff
        ):
            self.scope["last_update_datetime"] = datetime_now
            self.scope["backoff"] = self._initial_backoff
            event["notification"] = None
        elif self.scope["last_update_datetime"] > datetime_now - timedelta(
            seconds=self._initial_backoff
        ):
            self.scope["last_update_datetime"] = datetime_now + timedelta(
                seconds=self.scope["backoff"]
            )
            self.scope["backoff"] = self.scope["backoff"] + self._backoff_increment
            event["reload_widget"] = False
        else:
            self.scope["last_update_datetime"] = datetime_now
            self.scope["backoff"] = self._initial_backoff
        return event

    def send_updates(self, event):
        event = self.process_event_for_notification_storm(event)
        self.send(
            json.dumps(
                {
                    "type": "notification",
                    "notification_count": event["notification_count"],
                    "reload_widget": event["reload_widget"],
                    "notification": event["notification"],
                }
            )
        )

    def receive(self, text_data):
        if self._is_user_authenticated():
            try:
                json_data = json.loads(text_data)
            except json.JSONDecodeError:
                return

            try:
                if json_data["type"] == "notification":
                    self._notification_handler(
                        notification_id=json_data["notification_id"]
                    )
                elif json_data["type"] == "object_notification":
                    self._object_notification_handler(
                        object_id=json_data["object_id"],
                        app_label=json_data["app_label"],
                        model_name=json_data["model_name"],
                    )
            except KeyError:
                return

    def _notification_handler(self, notification_id):
        try:
            notification = Notification.objects.get(
                recipient=self.scope["user"], id=notification_id
            )
            notification.mark_as_read()
        except Notification.DoesNotExist:
            return

    def _object_notification_handler(self, object_id, app_label, model_name):
        try:
            object_notification = IgnoreObjectNotification.objects.get(
                user=self.scope["user"],
                object_id=object_id,
                object_content_type_id=ContentType.objects.get_by_natural_key(
                    app_label=app_label,
                    model=model_name,
                ).pk,
            )
            serialized_data = IgnoreObjectNotificationSerializer(object_notification)
            self.send(
                json.dumps(
                    {
                        "type": "object_notification",
                        "valid_till": serialized_data.data["valid_till"],
                    }
                )
            )
        except IgnoreObjectNotification.DoesNotExist:
            return

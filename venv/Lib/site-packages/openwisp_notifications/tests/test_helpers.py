from copy import deepcopy
from datetime import datetime
from unittest.mock import patch

from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpRequest
from django.utils import timezone

from openwisp_notifications.base.models import NOTIFICATION_CHOICES
from openwisp_notifications.swapper import load_model
from openwisp_notifications.tasks import ns_register_unregister_notification_type
from openwisp_notifications.types import NOTIFICATION_TYPES
from openwisp_notifications.types import (
    register_notification_type as base_register_notification_type,
)
from openwisp_notifications.types import (
    unregister_notification_type as base_unregister_notification_type,
)

Notification = load_model("Notification")
NotificationSetting = load_model("NotificationSetting")

TEST_DATETIME = datetime(2020, 5, 4, 0, 0, 0, 0, timezone.get_default_timezone())

test_notification_type = {
    "verbose_name": "Test Notification Type",
    "level": "test",
    "verb": "testing",
    "message": "{notification.verb} initiated by {notification.actor} since {notification}",
    "email_subject": "[{site.name}] {notification.verb} reported by {notification.actor}",
}


class MessagingRequest(HttpRequest):
    session = "session"

    def __init__(self):
        super(MessagingRequest, self).__init__()
        self._messages = FallbackStorage(self)

    def get_messages(self):
        return getattr(self._messages, "_queued_messages")

    def get_message_strings(self):
        return [str(m) for m in self.get_messages()]


def register_notification_type(type_name, type_config, models=[]):
    base_register_notification_type(type_name, type_config, models)
    ns_register_unregister_notification_type.delay(
        notification_type=type_name, delete_unregistered=False
    )
    # Update choices for model fields directly
    # Django loads field choices during model initialization, but our mocked
    # NOTIFICATION_CHOICES don't automatically update field choices.
    # We need to explicitly update the field choices to ensure the models
    # use our test environment's notification types.
    from openwisp_notifications.types import NOTIFICATION_CHOICES

    Notification._meta.get_field("type").choices = NOTIFICATION_CHOICES
    NotificationSetting._meta.get_field("type").choices = NOTIFICATION_CHOICES


def unregister_notification_type(type_name):
    base_unregister_notification_type(type_name)
    NotificationSetting.objects.filter(type=type_name).update(deleted=True)


def notification_related_object_url(obj, field, *args, **kwargs):
    related_obj = getattr(obj, field)
    return f"https://{related_obj}.example.com/index#heading"


def mock_notification_types(func):
    """
    This decorator mocks the NOTIFICATION_CHOICES and NOTIFICATION_TYPES
    to prevent polluting the test environment with any notification types
    registered during the test.
    """

    def wrapper(*args, **kwargs):
        with patch.multiple(
            "openwisp_notifications.types",
            NOTIFICATION_CHOICES=deepcopy(NOTIFICATION_CHOICES),
            NOTIFICATION_TYPES=deepcopy(NOTIFICATION_TYPES),
        ):
            return func(*args, **kwargs)

    return wrapper


class GetEditFormInlineMixin(object):
    def _get_org_edit_form_inline_params(self, user, org):
        params = super()._get_org_edit_form_inline_params(user, org)
        params.update(
            {
                # notification settings inline
                "notification_settings-TOTAL_FORMS": 1,
                "notification_settings-INITIAL_FORMS": 1,
                "notification_settings-MIN_NUM_FORMS": 0,
                "notification_settings-MAX_NUM_FORMS": 1,
            }
        )
        return params

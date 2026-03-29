# This file is based on django-notifications/notifications/base/models.py
# from the django-notifications project (BSD-3-Clause license).
# https://github.com/django-notifications/django-notifications
#
# It has been adapted to support the latest versions of Django and Python,
# as the original maintainers have not been active.
# See: https://github.com/django-notifications/django-notifications/pull/405

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import Choices


class NotificationQuerySet(models.query.QuerySet):
    """Notification QuerySet"""

    def unread(self, include_deleted=False):
        """Return only unread items in the current queryset"""
        return self.filter(unread=True)


class AbstractNotification(models.Model):

    LEVELS = Choices("success", "info", "warning", "error")
    level = models.CharField(
        _("level"), choices=LEVELS, default=LEVELS.info, max_length=20
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("recipient"),
        blank=False,
    )
    unread = models.BooleanField(_("unread"), default=True, blank=False, db_index=True)

    actor_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="notify_actor",
        verbose_name=_("actor content type"),
    )
    actor_object_id = models.CharField(_("actor object id"), max_length=255)
    actor = GenericForeignKey("actor_content_type", "actor_object_id")
    actor.short_description = _("actor")

    verb = models.CharField(_("verb"), max_length=255)
    description = models.TextField(_("description"), blank=True, null=True)

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="notify_target",
        verbose_name=_("target content type"),
        blank=True,
        null=True,
    )
    target_object_id = models.CharField(
        _("target object id"), max_length=255, blank=True, null=True
    )
    target = GenericForeignKey("target_content_type", "target_object_id")
    target.short_description = _("target")

    action_object_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="notify_action_object",
        verbose_name=_("action object content type"),
        blank=True,
        null=True,
    )
    action_object_object_id = models.CharField(
        _("action object object id"), max_length=255, blank=True, null=True
    )
    action_object = GenericForeignKey(
        "action_object_content_type", "action_object_object_id"
    )
    action_object.short_description = _("action object")

    timestamp = models.DateTimeField(
        _("timestamp"), default=timezone.now, db_index=True
    )

    public = models.BooleanField(_("public"), default=True, db_index=True)
    deleted = models.BooleanField(_("deleted"), default=False, db_index=True)
    emailed = models.BooleanField(_("emailed"), default=False, db_index=True)

    data = models.JSONField(_("data"), blank=True, null=True, encoder=DjangoJSONEncoder)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ("-timestamp",)
        # speed up notifications count query
        indexes = [
            models.Index(fields=["recipient", "unread"]),
        ]
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")

    def timesince(self, now=None):
        """
        Shortcut for the ``django.utils.timesince.timesince`` function of the
        current timestamp.
        """
        from django.utils.timesince import timesince as timesince_

        return timesince_(self.timestamp, now)

    def mark_as_read(self):
        if self.unread:
            self.unread = False
            self.save()

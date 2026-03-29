import logging
from contextlib import contextmanager

import django
import swapper
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models.constraints import UniqueConstraint
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import mark_safe
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from markdown import markdown
from swapper import get_model_name

from openwisp_notifications import settings as app_settings
from openwisp_notifications.exceptions import NotificationRenderException
from openwisp_notifications.types import (
    NOTIFICATION_CHOICES,
    get_notification_choices,
    get_notification_configuration,
)
from openwisp_notifications.utils import (
    _get_absolute_url,
    _get_object_link,
    send_notification_email,
)
from openwisp_utils.base import UUIDModel
from openwisp_utils.fields import FallbackBooleanChoiceField

from .notifications import AbstractNotification as BaseNotification

logger = logging.getLogger(__name__)


@contextmanager
def notification_render_attributes(obj, **attrs):
    """
    This context manager sets temporary attributes on
    the notification object to allowing rendering of
    notification.

    It can only be used to set aliases of the existing attributes.
    By default, it will set the following aliases:
        - actor_link -> actor_url
        - action_link -> action_url
        - target_link -> target_url
    """
    defaults = {
        "actor_link": "actor_url",
        "action_link": "action_url",
        "target_link": "target_url",
    }
    defaults.update(attrs)

    for target_attr, source_attr in defaults.items():
        setattr(obj, target_attr, getattr(obj, source_attr))

    # In Django 5.1+, GenericForeignKey fields defined in parent models can no longer
    # be overridden in child models (https://code.djangoproject.com/ticket/36295).
    # To avoid multiple database queries, we explicitly set these attributes here
    # using our cached _related_object method instead of relying on the default
    # GenericForeignKey accessor which would bypass our caching mechanism.
    setattr(obj, "actor", obj._related_object("actor"))
    setattr(obj, "action_object", obj._related_object("action_object"))
    setattr(obj, "target", obj._related_object("target"))

    yield obj

    for attr in defaults.keys():
        delattr(obj, attr)


class AbstractNotification(UUIDModel, BaseNotification):
    CACHE_KEY_PREFIX = "ow-notifications-"
    type = models.CharField(
        max_length=30,
        null=True,
        # TODO: Remove when dropping support for Django 4.2
        choices=(
            NOTIFICATION_CHOICES
            if django.VERSION < (5, 0)
            # In Django 5.0+, choices are normalized at model definition,
            # creating a static list of tuples that doesn't update when notification
            # types are dynamically registered or unregistered. Using a callable
            # ensures we always get the current choices from the registry.
            else get_notification_choices
        ),
        verbose_name=_("Notification Type"),
    )
    _actor = BaseNotification.actor
    _action_object = BaseNotification.action_object
    _target = BaseNotification.target

    class Meta(BaseNotification.Meta):
        abstract = True

    def __init__(self, *args, **kwargs):
        related_objs = [
            (opt, kwargs.pop(opt, None)) for opt in ("target", "action_object", "actor")
        ]
        super().__init__(*args, **kwargs)
        for opt, obj in related_objs:
            if obj is not None:
                setattr(self, f"{opt}_object_id", obj.pk)
                setattr(
                    self,
                    f"{opt}_content_type",
                    ContentType.objects.get_for_model(obj),
                )

    def __str__(self):
        return self.timesince()

    @classmethod
    def _cache_key(cls, *args):
        args = map(str, args)
        key = "-".join(args)
        return f"{cls.CACHE_KEY_PREFIX}{key}"

    @classmethod
    def count_cache_key(cls, user_pk):
        return cls._cache_key(f"unread-{user_pk}")

    @classmethod
    def invalidate_unread_cache(cls, user):
        """
        Invalidate unread cache for user.
        """
        cache.delete(cls.count_cache_key(user.pk))

    @classmethod
    def get_user_batched_notifications_cache_key(cls, user):
        if isinstance(user, get_user_model()):
            user = str(user.pk)
        return f"email_batch_{user}"

    @classmethod
    def get_user_batch_email_data(cls, user, pop=False):
        """
        Retrieve batch email notification data for a given user from the cache.

        Args:
            user (User): The user for whom to retrieve batch email data.
            pop (bool, optional): If True, delete the cached data after retrieval. Defaults to False.

        Returns:
            tuple: A tuple containing:
                - last_email_sent_time (datetime or None): The timestamp of the last sent email,
                    or None if not available.
                - start_time (datetime or None): The start time of the batch,
                    or None if not available.
                - pks (list): A list of primary keys associated with the batch,
                    or an empty list if not available.
        """
        key = cls.get_user_batched_notifications_cache_key(user)
        data = cache.get(key, {})
        if pop:
            cache.delete(key)
        return (
            data.get("last_email_sent_time", None),
            data.get("start_time", None),
            data.get("pks", []),
        )

    @classmethod
    def set_user_batch_email_data(cls, user, overwrite=True, **kwargs):
        """
        Set or update the batch email data for a specific user in the cache.

        This method stores or updates notification data associated with a user,
        which is used for batching email notifications. If `overwrite` is True,
        the existing data is replaced with the provided keyword arguments. If
        `overwrite` is False, the existing cached data is updated with the new
        keyword arguments.

        Args:
            user (User): The user for whom the batch email data is being set.
            overwrite (bool, optional): If True, overwrite existing data. If False,
                update existing data with new values. Defaults to True.
            **kwargs: Keyword arguments representing the data to be stored in the cache.
                (last_email_sent_time, start_time, pks)
        Returns:
            None
        """
        if overwrite:
            data = kwargs
        else:
            data = cache.get(cls.get_user_batched_notifications_cache_key(user), {})
            data.update(kwargs)
        cache.set(
            cls.get_user_batched_notifications_cache_key(user),
            data,
            timeout=None,
        )

    @classmethod
    def set_last_email_sent_time_for_user(cls, user, timestamp=None):
        timestamp = timestamp or timezone.now()
        cls.set_user_batch_email_data(
            user,
            last_email_sent_time=timestamp,
            overwrite=False,
        )

    def _get_related_object_url(self, field):
        """
        Returns URLs for "actor", "action_object" and "target" fields.
        """
        if self.type:
            # Generate URL according to the notification configuration
            config = get_notification_configuration(self.type)
            url = config.get(f"{field}_link", None)
            if url:
                try:
                    url_callable = import_string(url)
                    return url_callable(self, field=field, absolute_url=True)
                except ImportError:
                    return url
        return _get_object_link(obj=self._related_object(field), absolute_url=True)

    @property
    def actor_url(self):
        return self._get_related_object_url(field="actor")

    @property
    def action_url(self):
        return self._get_related_object_url(field="action_object")

    @property
    def target_url(self):
        return self._get_related_object_url(field="target")

    @cached_property
    def message(self):
        with notification_render_attributes(self):
            return self.get_message()

    @cached_property
    def rendered_description(self):
        if not self.description:
            return ""
        with notification_render_attributes(self):
            data = self.data or {}
            desc = self.description.format(notification=self, **data)
        return mark_safe(markdown(desc))

    @property
    def email_message(self):
        with notification_render_attributes(self, target_link="redirect_view_url"):
            return self.get_message()

    def get_message(self):
        if not self.type:
            return self.description
        try:
            config = get_notification_configuration(self.type)
            data = self.data or {}
            if "message" in data:
                md_text = data["message"].format(notification=self, **data)
            elif "message" in config:
                md_text = config["message"].format(notification=self, **data)
            else:
                md_text = render_to_string(
                    config["message_template"], context=dict(notification=self, **data)
                ).strip()
        except (AttributeError, KeyError, NotificationRenderException) as exception:
            self._invalid_notification(
                self.pk,
                exception,
                "Error encountered in rendering notification message",
            )
        return mark_safe(markdown(md_text))

    @cached_property
    def email_subject(self):
        if self.type:
            try:
                config = get_notification_configuration(self.type)
                data = self.data or {}
                return config["email_subject"].format(
                    site=Site.objects.get_current(), notification=self, **data
                )
            except (AttributeError, KeyError, NotificationRenderException) as exception:
                self._invalid_notification(
                    self.pk,
                    exception,
                    "Error encountered in generating notification email",
                )
        elif self.data.get("email_subject", None):
            return self.data.get("email_subject")
        else:
            return self.message

    def _related_object(self, field):
        obj_id = getattr(self, f"{field}_object_id")
        obj_content_type_id = getattr(self, f"{field}_content_type_id")
        if not obj_id:
            return
        cache_key = self._cache_key(obj_content_type_id, obj_id)
        obj = cache.get(cache_key)
        if not obj:
            try:
                obj = getattr(self, f"_{field}")
            except AttributeError:
                # Django 5.1+ no longer respects overridden GenericForeignKey fields in model definitions.
                # Using `_actor = BaseNotification.actor` doesn't work as expected.
                # We must manually fetch the related object using content type and object ID.
                # See: https://code.djangoproject.com/ticket/36295
                try:
                    obj = ContentType.objects.get_for_id(
                        obj_content_type_id
                    ).get_object_for_this_type(pk=obj_id)
                except ObjectDoesNotExist:
                    obj = None
            cache.set(
                cache_key,
                obj,
                timeout=app_settings.CACHE_TIMEOUT,
            )
        return obj

    def _invalid_notification(self, pk, exception, error_message):
        from openwisp_notifications.tasks import delete_notification

        logger.error(exception)
        delete_notification.delay(notification_id=pk)
        if isinstance(exception, NotificationRenderException):
            raise exception
        raise NotificationRenderException(error_message)

    @cached_property
    def actor(self):
        return self._related_object("actor")

    @cached_property
    def action_object(self):
        return self._related_object("action_object")

    @cached_property
    def target(self):
        return self._related_object("target")

    @property
    def redirect_view_url(self):
        return _get_absolute_url(
            reverse("notifications:notification_read_redirect", args=(self.pk,))
        )

    def send_email(self, force=False):
        """
        Send email notification to the user.
        """
        if self.emailed and not force:
            # If the notification is already emailed, do not send it again.
            return
        send_notification_email(self)
        self.emailed = True
        # bulk_update is used to prevent emitting post_save signal
        self._meta.model.objects.bulk_update([self], fields=["emailed"])


class AbstractNotificationSetting(UUIDModel):
    _RECEIVE_HELP = (
        "Note: Non-superadmin users receive "
        "notifications only for organizations "
        "of which they are member of."
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        # TODO: Remove when dropping support for Django 4.2
        choices=(
            NOTIFICATION_CHOICES
            if django.VERSION < (5, 0)
            # In Django 5.0+, choices are normalized at model definition,
            # creating a static list of tuples that doesn't update when notification
            # types are dynamically registered or unregistered. Using a callable
            # ensures we always get the current choices from the registry.
            else get_notification_choices
        ),
        verbose_name=_("Notification Type"),
    )
    organization = models.ForeignKey(
        get_model_name("openwisp_users", "Organization"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    web = models.BooleanField(
        _("web notifications"), null=True, blank=True, help_text=_(_RECEIVE_HELP)
    )
    email = models.BooleanField(
        _("email notifications"), null=True, blank=True, help_text=_(_RECEIVE_HELP)
    )
    deleted = models.BooleanField(_("Delete"), null=True, blank=True, default=False)

    class Meta:
        abstract = True
        constraints = [
            UniqueConstraint(
                fields=["organization", "type", "user"],
                name="unique_notification_setting",
            ),
        ]
        verbose_name = _("user notification settings")
        verbose_name_plural = verbose_name
        ordering = ["organization", "type"]
        indexes = [
            models.Index(fields=["type", "organization"]),
        ]

    def __str__(self):
        type_name = self.type_config.get("verbose_name", "Global Setting")
        if self.organization:
            return "{type} - {organization}".format(
                type=type_name,
                organization=self.organization,
            )
        else:
            return type_name

    def validate_global_setting(self):
        if self.organization is None and self.type is None:
            if (
                self.__class__.objects.filter(
                    user=self.user,
                    organization=None,
                    type=None,
                )
                .exclude(pk=self.pk)
                .exists()
            ):
                raise ValidationError("There can only be one global setting per user.")

    def save(self, *args, **kwargs):
        if not self.web_notification:
            self.email = self.web_notification
        with transaction.atomic():
            if not self.organization and not self.type:
                try:
                    previous_state = self.__class__.objects.only("email").get(
                        pk=self.pk
                    )
                    updates = {"web": self.web}

                    # If global web notifications are disabled, then disable email notifications as well
                    if not self.web:
                        updates["email"] = False

                    # Update email notifiations only if it's different from the previous state
                    # Otherwise, it would overwrite the email notification settings for specific
                    # setting that were enabled by the user after disabling global email notifications
                    if self.email != previous_state.email:
                        updates["email"] = self.email

                    self.user.notificationsetting_set.exclude(pk=self.pk).update(
                        **updates
                    )
                except self.__class__.DoesNotExist:
                    # Handle case when the object is being created
                    pass
        return super().save(*args, **kwargs)

    def full_clean(self, *args, **kwargs):
        self.validate_global_setting()
        if self.organization and self.type:
            if self.email == self.type_config["email_notification"]:
                self.email = None
            if self.web == self.type_config["web_notification"]:
                self.web = None
        return super().full_clean(*args, **kwargs)

    @property
    def type_config(self):
        return get_notification_configuration(self.type)

    @property
    def email_notification(self):
        if self.email is not None:
            return self.email
        return self.type_config.get("email_notification")

    @property
    def web_notification(self):
        if self.web is not None:
            return self.web
        return self.type_config.get("web_notification")

    @classmethod
    def email_notifications_enabled(cls, user):
        """Returns ``True`` if ``user`` has at least one email notification setting enabled."""
        return cls.objects.filter(user=user, email=True).exists()


class AbstractIgnoreObjectNotification(UUIDModel):
    """
    This model stores information about ignoring notification
    from a specific object for a user. Any instance of the model
    should be only stored until "valid_till" expires.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    object_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    object = GenericForeignKey("object_content_type", "object_id")
    valid_till = models.DateTimeField(null=True)

    class Meta:
        abstract = True
        ordering = ["valid_till"]


class AbstractOrganizationNotificationSettings(models.Model):
    organization = models.OneToOneField(
        swapper.get_model_name("openwisp_users", "Organization"),
        verbose_name=_("organization"),
        related_name="notification_settings",
        on_delete=models.CASCADE,
        primary_key=True,
    )
    web = FallbackBooleanChoiceField(
        fallback=app_settings.WEB_ENABLED,
        help_text=_(
            "Changing this value will affect the web notification settings of all "
            "users in the organization. Users will still be able to override "
            "this setting in their personal preferences."
        ),
        verbose_name=_("Web notifications enabled"),
    )
    email = FallbackBooleanChoiceField(
        fallback=app_settings.EMAIL_ENABLED,
        help_text=_(
            "Changing this value will affect the email notification settings of all "
            "users in the organization. Users will still be able to override "
            "this setting in their personal preferences."
        ),
        verbose_name=_("Email notifications enabled"),
    )

    class Meta:
        abstract = True
        verbose_name = _("organization notification settings")
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        if not self.web:
            self.email = False
        if not self._state.adding:
            self._update_organizationuser_settings()
        return super().save(*args, **kwargs)

    def _update_organizationuser_settings(self):
        try:
            db_instance = self.__class__.objects.only("web", "email").get(
                organization_id=self.organization_id
            )
        except self.__class__.DoesNotExist:
            return
        update_fields = {}
        for field in ["web", "email"]:
            if getattr(self, field) != getattr(db_instance, field):
                update_fields[field] = getattr(self, field)
        if update_fields:
            NotificationSetting = swapper.load_model(
                "openwisp_notifications", "NotificationSetting"
            )
            transaction.on_commit(
                lambda: NotificationSetting.objects.filter(
                    organization_id=self.organization_id
                ).update(**update_fields)
            )

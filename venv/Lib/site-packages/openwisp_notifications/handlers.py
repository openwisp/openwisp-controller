import logging
from urllib.parse import quote

from allauth.account.models import EmailAddress
from celery.exceptions import OperationalError
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.db.models.query import QuerySet
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext as _

from openwisp_notifications import settings as app_settings
from openwisp_notifications import tasks
from openwisp_notifications.exceptions import NotificationRenderException
from openwisp_notifications.swapper import load_model, swapper_load_model
from openwisp_notifications.types import (
    NOTIFICATION_ASSOCIATED_MODELS,
    get_notification_configuration,
)
from openwisp_notifications.utils import get_user_email_preference
from openwisp_notifications.websockets import handlers as ws_handlers

logger = logging.getLogger(__name__)

User = get_user_model()

Notification = load_model("Notification")
NotificationSetting = load_model("NotificationSetting")
OrganizationNotificationSettings = load_model("OrganizationNotificationSettings")
IgnoreObjectNotification = load_model("IgnoreObjectNotification")

Group = swapper_load_model("openwisp_users", "Group")
OrganizationUser = swapper_load_model("openwisp_users", "OrganizationUser")
Organization = swapper_load_model("openwisp_users", "Organization")


def notify_handler(**kwargs):
    """
    Handler function to create Notification instance upon action signal call.
    """
    # Pull the options out of kwargs
    kwargs.pop("signal", None)
    actor = kwargs.pop("sender")
    public = bool(kwargs.pop("public", True))
    description = kwargs.pop("description", None)
    timestamp = kwargs.pop("timestamp", timezone.now())
    recipient = kwargs.pop("recipient", None)
    notification_type = kwargs.pop("type", None)
    target = kwargs.get("target", None)
    target_org = getattr(target, "organization_id", None)
    try:
        notification_template = get_notification_configuration(notification_type)
    except NotificationRenderException as error:
        logger.error(f"Error encountered while creating notification: {error}")
        return
    level = kwargs.pop(
        "level", notification_template.get("level", Notification.LEVELS.info)
    )
    verb = notification_template.get("verb", kwargs.pop("verb", None))
    user_app_name = User._meta.app_label

    where = Q(is_superuser=True)
    not_where = Q()
    where_group = Q()
    if target_org:
        org_admin_query = Q(
            **{
                f"{user_app_name}_organizationuser__organization": target_org,
                f"{user_app_name}_organizationuser__is_admin": True,
            }
        )
        where = where | (Q(is_staff=True) & org_admin_query)
        where_group = org_admin_query

        # We can only find notification setting if notification type and
        # target organization is present.
        if notification_type:
            # Create notification for users who have opted for receiving notifications.
            # For users who have not configured web_notifications,
            # use default from notification type
            web_notification = Q(notificationsetting__web=True)
            if notification_template["web_notification"]:
                web_notification |= Q(notificationsetting__web=None)

            notification_setting = web_notification & Q(
                notificationsetting__type=notification_type,
                notificationsetting__organization_id=target_org,
                notificationsetting__deleted=False,
            )
            where = where & notification_setting
            where_group = where_group & notification_setting

    # Ensure notifications are only sent to active user
    where = where & Q(is_active=True)
    where_group = where_group & Q(is_active=True)

    # We can only find ignore notification setting if target object is present
    if target:
        not_where = Q(
            ignoreobjectnotification__object_id=target.pk,
            ignoreobjectnotification__object_content_type=ContentType.objects.get_for_model(
                target._meta.model
            ),
        ) & (
            Q(ignoreobjectnotification__valid_till=None)
            | Q(ignoreobjectnotification__valid_till__gt=timezone.now())
        )

    if recipient:
        # Check if recipient is User, Group or QuerySet
        if isinstance(recipient, Group):
            recipients = recipient.user_set.filter(where_group)
        elif isinstance(recipient, QuerySet):
            recipients = recipient.distinct()
        elif isinstance(recipient, list):
            recipients = recipient
        else:
            recipients = [recipient]
    else:
        recipients = (
            User.objects.prefetch_related(
                "notificationsetting_set", "ignoreobjectnotification_set"
            )
            .order_by("date_joined")
            .filter(where)
            .exclude(not_where)
            .distinct()
        )
    optional_objs = [
        (kwargs.pop(opt, None), opt) for opt in ("target", "action_object")
    ]

    notification_list = []
    for recipient in recipients:
        notification = Notification(
            recipient=recipient,
            actor=actor,
            verb=str(verb),
            public=public,
            description=description,
            timestamp=timestamp,
            level=level,
            type=notification_type,
        )

        # Set optional objects
        for obj, opt in optional_objs:
            if obj is not None:
                setattr(notification, "%s_object_id" % opt, obj.pk)
                setattr(
                    notification,
                    "%s_content_type" % opt,
                    ContentType.objects.get_for_model(obj),
                )
        if kwargs:
            notification.data = kwargs
        notification.save()
        notification_list.append(notification)

    return notification_list


@receiver(post_save, sender=Notification, dispatch_uid="send_email_notification")
def send_email_notification(sender, instance, created, **kwargs):
    # Abort if a new notification is not created
    if not created:
        return

    email_verified = instance.recipient.emailaddress_set.filter(
        verified=True, email=instance.recipient.email
    ).exists()
    if not email_verified or not get_user_email_preference(instance):
        return
    if not app_settings.EMAIL_BATCH_INTERVAL:
        instance.send_email()
        return
    last_email_sent_time, batch_start_time, batched_notifications = (
        Notification.get_user_batch_email_data(instance.recipient)
    )
    # Send a single email if:
    # 1. The user has not received any email yet
    # 2. The last email was sent more than EMAIL_BATCH_INTERVAL seconds ago and
    #    no batch is scheduled
    if not last_email_sent_time or (
        not batch_start_time
        and (
            # More than EMAIL_BATCH_INTERVAL seconds have passed since the last email was sent
            last_email_sent_time
            < (
                timezone.now()
                - timezone.timedelta(seconds=app_settings.EMAIL_BATCH_INTERVAL)
            )
        )
    ):
        instance.send_email()
        Notification.set_last_email_sent_time_for_user(
            instance.recipient, instance.timestamp
        )
        return
    batched_notifications.append(instance.id)
    Notification.set_user_batch_email_data(
        instance.recipient,
        last_email_sent_time=last_email_sent_time,
        start_time=batch_start_time or instance.timestamp,
        pks=batched_notifications,
    )
    # If no batch was scheduled, schedule a new one
    if not batch_start_time:
        tasks.send_batched_email_notifications.apply_async(
            (str(instance.recipient.pk),),
            countdown=app_settings.EMAIL_BATCH_INTERVAL,
        )
    elif (
        batch_start_time
        + timezone.timedelta(seconds=app_settings.EMAIL_BATCH_INTERVAL * 1.25)
    ) < timezone.now():
        # The celery task failed to execute in the expected time.
        # This could happen when the celery worker is overloaded.
        # Send the email immediately.
        tasks.send_batched_email_notifications(
            instance.recipient.pk,
        )


@receiver(post_save, sender=Notification, dispatch_uid="clear_notification_cache_saved")
@receiver(
    post_delete, sender=Notification, dispatch_uid="clear_notification_cache_deleted"
)
def clear_notification_cache(sender, instance, **kwargs):
    Notification.invalidate_unread_cache(instance.recipient)
    # Reload notification widget only if notification is created or deleted
    # Display notification toast when a new notification is created
    ws_handlers.notification_update_handler(
        recipient=instance.recipient,
        reload_widget=kwargs.get("created", True),
        notification=instance if kwargs.get("created", None) else None,
    )


@receiver(post_delete, dispatch_uid="delete_obsolete_objects")
def related_object_deleted(sender, instance, **kwargs):
    """
    Delete Notification and IgnoreObjectNotification objects having
    "instance" as related object.
    """
    if sender not in NOTIFICATION_ASSOCIATED_MODELS:
        return
    instance_id = getattr(instance, "pk", None)
    if instance_id:
        instance_model = instance._meta.model_name
        instance_app_label = instance._meta.app_label
        tasks.delete_obsolete_objects.delay(
            instance_app_label, instance_model, instance_id
        )


@receiver(
    post_save, sender=Organization, dispatch_uid="create_org_notification_settings"
)
def create_org_notification_settings(created, instance, **kwargs):
    if not created:
        return
    org_setting = OrganizationNotificationSettings(organization=instance)
    org_setting.full_clean()
    org_setting.save()


def notification_type_registered_unregistered_handler(sender, **kwargs):
    try:
        tasks.ns_register_unregister_notification_type.delay()
    except OperationalError:
        logger.warn(
            "\tCelery broker is unreachable, skipping populating data for user(s) "
            "notification preference(s).\n"
            "\tMake sure that celery broker is running and reachable by celery workers.\n"
            "\tYou can use following command later "
            "to populate data for user(s) notification preference(s).\n\n"
            "\t\t python manage.py populate_notification_preferences\n"
        )


@receiver(
    post_save,
    sender=OrganizationUser,
    dispatch_uid="create_orguser_notification_setting",
)
def organization_user_post_save(instance, created, **kwargs):
    transaction.on_commit(
        lambda: tasks.update_org_user_notificationsetting.delay(
            org_user_id=instance.pk,
            user_id=instance.user_id,
            org_id=instance.organization_id,
            is_org_admin=instance.is_admin,
        )
    )


@receiver(
    post_delete,
    sender=OrganizationUser,
    dispatch_uid="delete_orguser_notification_setting",
)
def notification_setting_delete_org_user(instance, **kwargs):
    tasks.ns_organization_user_deleted.delay(
        user_id=instance.user_id, org_id=instance.organization_id
    )


@receiver(pre_save, sender=User, dispatch_uid="superuser_demoted_notification_setting")
def superuser_status_changed_notification_setting(instance, update_fields, **kwargs):
    """
    If user is demoted from superuser status, then
    remove notification settings for non-managed organizations.

    If user is promoted to superuser, then
    create notification settings for all organizations.
    """
    if update_fields is not None and "is_superuser" not in update_fields:
        # No-op if is_superuser field is not being updated.
        # If update_fields is None, it means any field could be updated.
        return
    try:
        db_instance = User.objects.only("is_superuser").get(pk=instance.pk)
    except User.DoesNotExist:
        # User is being created
        return
    # If user is demoted from superuser to non-superuser
    if db_instance.is_superuser and not instance.is_superuser:
        transaction.on_commit(
            lambda: tasks.superuser_demoted_notification_setting.delay(instance.pk)
        )
    elif not db_instance.is_superuser and instance.is_superuser:
        transaction.on_commit(
            lambda: tasks.create_superuser_notification_settings.delay(instance.pk)
        )


@receiver(post_save, sender=User, dispatch_uid="create_superuser_notification_settings")
def create_superuser_notification_settings(instance, created, **kwargs):
    if created and instance.is_superuser:
        transaction.on_commit(
            lambda: tasks.create_superuser_notification_settings.delay(instance.pk)
        )


@receiver(
    post_save, sender=Organization, dispatch_uid="org_created_notification_setting"
)
def notification_setting_org_created(created, instance, **kwargs):
    if created:
        transaction.on_commit(lambda: tasks.ns_organization_created.delay(instance.pk))


@receiver(
    post_save,
    sender=IgnoreObjectNotification,
    dispatch_uid="schedule_object_notification_deletion",
)
def schedule_object_notification_deletion(instance, created, **kwargs):
    if instance.valid_till is not None:
        tasks.delete_ignore_object_notification.apply_async(
            (instance.pk,), eta=instance.valid_till
        )


def register_notification_cache_update(model, signal, dispatch_uid=None):
    signal.connect(
        update_notification_cache,
        sender=model,
        dispatch_uid=dispatch_uid,
    )


def update_notification_cache(sender, instance, **kwargs):
    def invalidate_cache():
        content_type = ContentType.objects.get_for_model(instance)
        cache_key = Notification._cache_key(content_type.id, instance.id)
        cache.delete(cache_key)

    # execute cache invalidation only after changes have been committed to the DB
    transaction.on_commit(invalidate_cache)


@receiver(user_logged_in)
def check_email_verification(sender, user, request, **kwargs):
    admin_path = reverse("admin:index")
    # abort if this is not an admin login
    if not user.is_staff or not request.path.startswith(admin_path):
        return
    if not NotificationSetting.email_notifications_enabled(user):
        return
    has_verified_email = EmailAddress.objects.filter(user=user, verified=True).exists()
    # abort if user already has a verified email
    # or doesn't have an email at all
    if has_verified_email or not user.email:
        return
    # add a warning UX message encouraging the user
    # to verify his email address
    next_path = request.POST.get(
        "next", request.GET.get("next", reverse("admin:index"))
    )
    current_path = quote(next_path)
    resend_path = reverse("notifications:resend_verification_email")
    resend_url = f"{resend_path}?next={current_path}"
    message = format_html(
        _(
            "Email notifications are enabled, but emails cannot "
            "be sent because your email address is not verified. "
            'Please <a href="{}">verify your email address</a> '
            "to enable email notifications."
        ),
        resend_url,
    )
    messages.warning(request, message)

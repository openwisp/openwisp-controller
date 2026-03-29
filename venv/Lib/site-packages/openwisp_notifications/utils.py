import json

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _
from django.utils.translation import ngettext_lazy

from openwisp_notifications import settings as app_settings
from openwisp_notifications.exceptions import NotificationRenderException
from openwisp_notifications.swapper import load_model
from openwisp_utils.admin_theme.email import send_email

from .tokens import email_token_generator


def _get_object_link(obj, absolute_url=False, *args, **kwargs):
    try:
        url = reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
            args=[obj.id],
        )
        if absolute_url:
            url = _get_absolute_url(url)
        return url
    except (NoReverseMatch, AttributeError):
        return "#"


def _get_absolute_url(path):
    site = Site.objects.get_current()
    protocol = "http" if getattr(settings, "DEBUG", False) else "https"
    return f"{protocol}://{site.domain}{path}"


def normalize_unread_count(unread_count):
    if unread_count > 99:
        return "99+"
    else:
        return unread_count


def get_unsubscribe_url_for_user(user, full_url=True):
    token = email_token_generator.make_token(user)
    data = json.dumps({"user_id": str(user.id), "token": token})
    encoded_data = urlsafe_base64_encode(force_bytes(data))
    unsubscribe_path = reverse("notifications:unsubscribe")
    if not full_url:
        return f"{unsubscribe_path}?token={encoded_data}"
    current_site = Site.objects.get_current()
    return f"https://{current_site.domain}{unsubscribe_path}?token={encoded_data}"


def get_unsubscribe_url_email_footer(url):
    return render_to_string(
        "openwisp_notifications/emails/unsubscribe_footer.html",
        {"unsubscribe_url": url},
    )


def send_notification_email(
    notifications,
    since=None,
    notifications_count=0,
    user=None,
):

    extra_context = {}
    current_site = Site.objects.get_current()
    if isinstance(notifications, load_model("Notification")):
        user = notifications.recipient
        since = notifications.timestamp
        notifications_count = 1
        notifications = [notifications]
    unsent_notifications = []
    for notification in notifications[: app_settings.EMAIL_BATCH_DISPLAY_LIMIT]:
        url = notification.data.get("url", "") if notification.data else None
        if url:
            notification.url = url
        elif notification.target:
            notification.url = notification.redirect_view_url
        else:
            notification.url = None
        try:
            notification.email_message
        except NotificationRenderException:
            continue
        else:
            unsent_notifications.append(notification)
    if not unsent_notifications:
        return
    unsubscribe_url = get_unsubscribe_url_for_user(user)
    pluralize_notification = ngettext_lazy(
        "notification", "notifications", notifications_count
    )
    since = timezone.localtime(since).strftime("%B %-d, %Y, %-I:%M %p %Z")
    extra_context = {
        "notifications": unsent_notifications,
        "notifications_count": notifications_count,
        "site_name": current_site.name,
        "footer": get_unsubscribe_url_email_footer(unsubscribe_url),
        "subtitle": _("Since {since}").format(since=since),
        "since": since,
        "title": _("{notifications_count} unread {pluralize_notification}").format(
            notifications_count=notifications_count,
            pluralize_notification=pluralize_notification,
        ),
    }
    if notifications_count == 1:
        extra_context.update(
            {
                "call_to_action_url": unsent_notifications[0].url,
                "call_to_action_text": _("View Details"),
            }
        )
        subject = unsent_notifications[0].email_subject
    else:
        if notifications_count > app_settings.EMAIL_BATCH_DISPLAY_LIMIT:
            extra_context.update(
                {
                    "call_to_action_url": f"https://{current_site.domain}/admin/#notifications",
                    "call_to_action_text": _("View all Notifications"),
                }
            )
        notifications_count = min(
            notifications_count, app_settings.EMAIL_BATCH_DISPLAY_LIMIT
        )
        subject = _(
            "[{site_name}] {notifications_count} unread {pluralize_notification} since {since}"
        ).format(
            site_name=current_site.name,
            notifications_count=notifications_count,
            since=since,
            pluralize_notification=pluralize_notification,
        )

    plain_text_content = render_to_string(
        "openwisp_notifications/emails/notification.txt", extra_context
    )
    send_email(
        subject=subject,
        body_text=plain_text_content,
        body_html=True,
        recipients=[user.email],
        extra_context=extra_context,
        headers={
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            "List-Unsubscribe": f"<{unsubscribe_url}>",
        },
        html_email_template="openwisp_notifications/emails/notification.html",
    )


def get_user_email_preference(notification):
    """
    Returns the user's email preference for notifications.
    If the user has no preference set, it defaults to True.
    """
    target_org = getattr(getattr(notification, "target", None), "organization_id", None)
    if not (notification.type and target_org):
        # We can not check email preference if notification type is absent,
        # or if target_org is not present
        # therefore send email anyway.
        return True
    try:
        return notification.recipient.notificationsetting_set.get(
            organization=target_org, type=notification.type
        ).email_notification
    except ObjectDoesNotExist:
        return False

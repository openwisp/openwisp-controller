import json
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch
from uuid import uuid4

from allauth.account.models import EmailAddress
from celery.exceptions import OperationalError
from django.apps.registry import apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import post_migrate, post_save
from django.template import TemplateDoesNotExist
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import Promise
from django.utils.timesince import timesince
from django.utils.translation import gettext_lazy
from freezegun import freeze_time

from openwisp_notifications import settings as app_settings
from openwisp_notifications import tasks, utils
from openwisp_notifications.exceptions import NotificationRenderException
from openwisp_notifications.handlers import (
    notify_handler,
    register_notification_cache_update,
)
from openwisp_notifications.signals import notify
from openwisp_notifications.swapper import load_model, swapper_load_model
from openwisp_notifications.tests.test_helpers import (
    mock_notification_types,
    register_notification_type,
    test_notification_type,
    unregister_notification_type,
)
from openwisp_notifications.tokens import email_token_generator
from openwisp_notifications.types import (
    _unregister_notification_choice,
    get_notification_configuration,
)
from openwisp_notifications.utils import _get_absolute_url, get_unsubscribe_url_for_user
from openwisp_users.tests.utils import TestOrganizationMixin
from openwisp_utils.tests import capture_any_output

from . import (
    _test_batch_email_notification_email_body,
    _test_batch_email_notification_email_html,
)

User = get_user_model()
OrganizationUser = swapper_load_model("openwisp_users", "OrganizationUser")
Group = swapper_load_model("openwisp_users", "Group")
Notification = load_model("Notification")
NotificationSetting = load_model("NotificationSetting")
NotificationAppConfig = apps.get_app_config(Notification._meta.app_label)
# reused across tests
start_time = timezone.now()
ten_minutes_ago = start_time - timedelta(minutes=10)
notification_queryset = Notification.objects.order_by("-timestamp")


class TestNotifications(TestOrganizationMixin, TransactionTestCase):
    app_label = "openwisp_notifications"
    users_app_label = "openwisp_users"

    def setUp(self):
        self.admin = self._create_admin()
        self.notification_options = dict(
            sender=self.admin,
            description="Test Notification",
            verb="Test Notification",
            email_subject="Test Email subject",
            url="https://localhost:8000/admin",
        )

    def _create_notification(self, **kwargs):
        return notify.send(**self.notification_options, **kwargs)

    def test_create_notification(self):
        operator = super()._create_operator()
        data = dict(
            email_subject="Test Email subject", url="https://localhost:8000/admin"
        )
        n = Notification.objects.create(
            actor=self.admin,
            recipient=self.admin,
            description="Test Notification Description",
            verb="Test Notification",
            action_object=operator,
            target=operator,
            data=data,
        )
        self.assertEqual(str(n), timesince(n.timestamp, timezone.now()))
        self.assertEqual(n.actor_object_id, self.admin.id)
        self.assertEqual(
            n.actor_content_type, ContentType.objects.get_for_model(self.admin)
        )
        self.assertEqual(n.action_object_object_id, operator.id)
        self.assertEqual(
            n.action_object_content_type, ContentType.objects.get_for_model(operator)
        )
        self.assertEqual(n.target_object_id, operator.id)
        self.assertEqual(
            n.target_content_type, ContentType.objects.get_for_model(operator)
        )
        self.assertEqual(n.verb, "Test Notification")
        self.assertEqual(n.message, "Test Notification Description")
        self.assertEqual(n.recipient, self.admin)

    def test_lazy_translation(self):
        """
        Regression test for issue #438.
        Test that notifications with lazy translation objects in data
        can be saved without raising a TypeError.
        """
        # Using gettext_lazy in notification data should not fail
        notification_options = dict(
            sender=self.admin,
            description=gettext_lazy("Test Notification"),
            verb=gettext_lazy("Test Notification"),
            email_subject=gettext_lazy("Test Email subject"),
            url="https://localhost:8000/admin",
            message=gettext_lazy("Translated message"),
            random=gettext_lazy("any extra kwargs is evaluated"),
        )
        # Must not raise TypeError: Object of type __proxy__ is not JSON serializable
        notify.send(**notification_options)
        self.assertEqual(notification_queryset.count(), 1)
        n = notification_queryset.first()
        # Verify the message was stored as a plain string, not a proxy object
        self.assertEqual(n.data.get("message"), "Translated message")
        # Verify the stored value is not a lazy proxy object
        self.assertNotIsInstance(n.data.get("message"), Promise)

    @mock_notification_types
    def test_create_with_extra_data(self):
        register_notification_type(
            "error_type",
            {
                "verbose_name": "Error",
                "level": "error",
                "verb": "error",
                "message": "Error: {error}",
                "email_subject": "Error subject: {error}",
            },
        )
        error = "500 Internal Server Error"
        notify.send(
            type="error_type",
            url="https://localhost:8000/admin",
            recipient=self.admin,
            sender=self.admin,
            error=error,
        )
        self.assertEqual(notification_queryset.count(), 1)
        n = notification_queryset.first()
        self.assertIn(f"Error: {error}", n.message)
        self.assertEqual(n.email_subject, f"Error subject: {error}")

    def test_batch_email_helpers(self):
        with self.subTest("get_user_batched_notifications_cache_key()"):
            cache_key = Notification.get_user_batched_notifications_cache_key(
                self.admin.pk
            )
            self.assertEqual(
                cache_key,
                f"email_batch_{self.admin.pk}",
            )

        with self.subTest("set_user_batch_email_data()"):
            last_email_sent_time = ten_minutes_ago
            now = timezone.now()
            Notification.set_user_batch_email_data(
                self.admin.pk,
                last_email_sent_time=last_email_sent_time,
                start_time=now,
                pks=[1],
            )
            cached_data = cache.get(cache_key)
            self.assertEqual(cached_data["last_email_sent_time"], last_email_sent_time)
            self.assertEqual(cached_data["start_time"], now)
            self.assertEqual(cached_data["pks"], [1])

            # Test overwriting existing cache data
            Notification.set_user_batch_email_data(
                self.admin.pk, last_email_sent_time=now, overwrite=True
            )
            cached_data = cache.get(cache_key)
            self.assertEqual(cached_data["last_email_sent_time"], now)
            self.assertNotIn("start_time", cached_data)
            self.assertNotIn("pks", cached_data)

        with self.subTest("get_user_batch_email_data()"):
            # pop = True means it will remove the data from cache
            last_email_sent_time, start_time, pks = (
                Notification.get_user_batch_email_data(self.admin.pk, pop=True)
            )
            self.assertEqual(last_email_sent_time, now)
            self.assertEqual(start_time, None)
            self.assertEqual(pks, [])
            self.assertEqual(cache.get(cache_key), None)

    @patch("openwisp_notifications.base.models.send_notification_email")
    def test_send_email(self, mocked_send_email):
        self.admin.emailaddress_set.update(verified=True)
        notification = self._create_notification().pop()[1][0]
        mocked_send_email.assert_called_once()
        notification.refresh_from_db()
        self.assertEqual(notification.emailed, True)

        mocked_send_email.reset_mock()
        with self.subTest("Calling send_email does not send duplicate email"):
            notification.send_email()
            mocked_send_email.assert_not_called()

        with self.subTest("Calling send_email with force=True sends email again"):
            notification.send_email(force=True)
            mocked_send_email.assert_called_once()

    def test_superuser_notifications_disabled(self):
        target_obj = self._get_org_user()
        self.notification_options.update({"type": "default", "target": target_obj})
        notification_preference = NotificationSetting.objects.get(
            user_id=self.admin.pk,
            organization_id=target_obj.organization.pk,
            type="default",
        )
        # Database field is set to None
        self.assertEqual(notification_preference.email, None)
        # The fallback is taked from notification type
        self.assertTrue(notification_preference.email_notification)
        notification_preference.web = False
        notification_preference.full_clean()
        notification_preference.save()
        notification_preference.refresh_from_db()
        # The database field has been updated to override the default
        # value in notification type.
        self.assertEqual(notification_preference.email, False)
        self._create_notification()
        self.assertEqual(notification_queryset.count(), 0)

    def test_email_sent(self):
        self._create_notification()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.admin.email])
        n = notification_queryset.first()
        self.assertEqual(
            mail.outbox[0].subject,
            "Test Email subject",
        )
        self.assertIn(n.message, mail.outbox[0].body)
        self.assertIn(n.data.get("url"), mail.outbox[0].body)
        self.assertIn("https://", n.data.get("url"))
        html_email = mail.outbox[0].alternatives[0][0]
        self.assertIn(
            '<div class="email-title">1 unread notification</div>', html_email
        )

    def test_email_disabled(self):
        self.notification_options.update(
            {"type": "default", "target": self._get_org_user()}
        )
        NotificationSetting.objects.filter(
            user_id=self.admin.pk, type="default"
        ).update(email=False)
        self._create_notification()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_notification_preference_flagged_deleted(self):
        self.notification_options.update(
            {"type": "default", "target": self._get_org_user()}
        )
        NotificationSetting.objects.filter(
            user_id=self.admin.pk, type="default"
        ).update(deleted=True)
        self._create_notification()
        self.assertEqual(Notification.objects.count(), 0)

    def test_notification_preference_deleted_from_db(self):
        self.notification_options.update(
            {"type": "default", "target": self._get_org_user()}
        )
        NotificationSetting.objects.filter(
            user_id=self.admin.pk, type="default"
        ).delete()
        self._create_notification()
        self.assertEqual(Notification.objects.count(), 0)

    def test_email_not_present(self):
        self.admin.email = ""
        self.admin.save()
        self._create_notification()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_group_recipient(self):
        org = self._get_org()
        operator = self._get_operator()
        user = self._create_user(
            username="user", email="user@user.com", first_name="User", last_name="user"
        )
        op_group = Group.objects.create(name="Operator")
        op_group.user_set.add(operator)
        op_group.user_set.add(user)
        op_group.save()
        self.notification_options.update({"recipient": op_group, "type": "default"})
        recipients = (operator, user)

        # Test for group with no target object
        n = self._create_notification().pop()
        if n[0] is notify_handler:
            notifications = n[1]
            self.assertEqual(len(notifications), 2)
            for notification, recipient in zip(notifications, recipients):
                self.assertEqual(notification.recipient, recipient)
        else:
            self.fail()

        # Test for group with target object of another organization
        org = self._get_org()
        target = self._create_user(
            username="target",
            email="target@target.com",
            first_name="Target",
            last_name="user",
        )
        self._create_org_user(user=target, organization=org)
        target.organization_id = org.id
        self.notification_options.update({"target": target})
        self._create_notification()
        # No new notification should be created
        self.assertEqual(notification_queryset.count(), 2)

        # Test for group with target object of same organization
        # Adding operator to organization of target object
        self._create_org_user(user=operator, organization=org, is_admin=True)
        self._create_notification()
        self.assertEqual(notification_queryset.count(), 3)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, operator)

    def test_queryset_recipient(self):
        super()._create_operator()
        users = User.objects.all()
        self.notification_options.update({"recipient": users})
        n = self._create_notification().pop()
        if n[0] is notify_handler:
            notifications = n[1]
            for notification, user in zip(notifications, users):
                self.assertEqual(notification.recipient, user)
        else:
            self.fail()

    def test_description_in_email_subject(self):
        self.notification_options.pop("email_subject")
        self._create_notification()
        self.assertEqual(
            mail.outbox[0].subject,
            "Test Notification",
        )

    def test_handler_optional_tag(self):
        operator = self._create_operator()
        self.notification_options.update({"action_object": operator})
        self._create_notification()
        n = notification_queryset.first()
        self.assertEqual(
            n.action_object_content_type, ContentType.objects.get_for_model(operator)
        )
        self.assertEqual(n.action_object_object_id, str(operator.id))

    def test_organization_recipient(self):
        self.notification_options.update({"type": "default"})
        testorg = self._create_org()
        operator = self._create_operator()
        user = self._create_user(is_staff=False)
        OrganizationUser.objects.create(user=user, organization=testorg)
        OrganizationUser.objects.create(user=operator, organization=testorg)
        recipients = (self.admin, operator)
        operator.organization_id = testorg.id
        self.notification_options.update({"target": operator})
        n = self._create_notification().pop()
        if n[0] is notify_handler:
            notifications = n[1]
            for notification, recipient in zip(notifications, recipients):
                self.assertEqual(notification.recipient, recipient)
        else:
            self.fail()

    def test_no_organization(self):
        # Tests no target object is present
        self.notification_options.update({"type": "default"})
        self._create_org_user()
        user = self._create_user(
            username="user",
            email="user@user.com",
            first_name="User",
            last_name="user",
            is_staff=False,
        )
        self._create_notification()
        # Only superadmin should receive notification
        self.assertEqual(notification_queryset.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.actor, self.admin)
        self.assertEqual(n.recipient, self.admin)

        # Tests no user from organization of target object
        org = self._create_org(name="test_org")
        OrganizationUser.objects.create(user=user, organization=org)
        self.notification_options.update({"target": user})
        self._create_notification()
        self.assertEqual(notification_queryset.count(), 2)
        # Only superadmin should receive notification
        n = notification_queryset.first()
        self.assertEqual(n.actor, self.admin)
        self.assertEqual(n.recipient, self.admin)
        self.assertEqual(n.target, user)

    def test_default_notification_type(self):
        self.notification_options.pop("verb")
        self.notification_options.pop("url")
        self.notification_options.update(
            {"type": "default", "target": self._get_org_user()}
        )
        self._create_notification()
        n = notification_queryset.first()
        self.assertEqual(n.level, "info")
        self.assertEqual(n.verb, "default verb")
        self.assertIn(
            "Default notification with default verb and level info by", n.message
        )
        self.assertEqual(n.email_subject, "[example.com] Default Notification Subject")
        email = mail.outbox.pop()
        html_email = email.alternatives[0][0]
        timestamp = timezone.localtime(n.timestamp).strftime("%B %-d, %Y, %-I:%M %p %Z")
        self.assertEqual(
            email.body,
            (
                f"\n\n[example.com] 1 unread notifications since {timestamp}"
                "\n\n\n- Default notification with default verb and level info by Tester Tester (test org)"
                "\n  Description: Test Notification"
                f"\n  Date & Time: {timestamp}"
                f"\n  URL: {n.redirect_view_url}\n\n\n\n"
            ),
        )
        self.assertInHTML(
            (
                f'<a class="alert-link" href="{n.redirect_view_url}" target="_blank">'
                '  <table class="alert">'
                "    <tbody>"
                "      <tr>"
                "        <td>"
                '          <div> <span class="badge info">info</span>'
                '            <div class="title">'
                "              <p>Default notification with default verb and level info by Tester Tester"
                "                 (test org)</p>"
                "            </div>"
                "          </div>"
                "        </td>"
                '        <td class="right-arrow-container"> <img class="right-arrow"'
                '            src="https://example.com/static/ui/openwisp/images/right-arrow.png"'
                '            alt="right-arrow"> </td>'
                "      </tr>"
                "      <tr>"
                "        <td>"
                "          <hr>"
                "          <div>"
                f'            <p class="timestamp">{timestamp}</p>'
                "          </div>"
                "        </td>"
                "      </tr>"
                "    </tbody>"
                "  </table>"
                "</a>"
            ),
            html_email,
        )

    def test_generic_notification_type(self):
        self.notification_options.pop("verb")
        self.notification_options.update(
            {
                "message": "[{notification.actor}]({notification.actor_link})",
                "type": "generic_message",
                "description": "[{notification.actor}]({notification.actor_link})",
            }
        )
        self._create_notification()
        n = notification_queryset.first()
        self.assertEqual(n.level, "info")
        self.assertEqual(n.verb, "generic verb")
        expected_output = (
            '<p><a href="https://example.com{user_path}">admin</a></p>'
        ).format(
            user_path=reverse(
                f"admin:{self.users_app_label}_user_change", args=[self.admin.pk]
            )
        )
        self.assertEqual(n.message, expected_output)
        self.assertEqual(n.rendered_description, expected_output)
        self.assertEqual(n.email_subject, "[example.com] Generic Notification Subject")

    def test_generic_notification_type_global_notifications_disabled(self):
        org_user = self._get_org_user()
        self.notification_options.pop("verb")
        self.notification_options.update(
            {
                "message": "[{notification.target}]({notification.target_link})",
                "type": "generic_message",
                "description": "[{notification.target}]({notification.target_link})",
                "target": org_user,
            }
        )
        global_setting = self.admin.notificationsetting_set.get(
            type=None, organization=None
        )
        global_setting.web = False
        global_setting.full_clean()
        global_setting.save()
        self._create_notification()
        self.assertEqual(notification_queryset.count(), 0)

    def test_notification_level_kwarg_precedence(self):
        # Create a notification with level kwarg set to 'warning'
        self.notification_options.update({"level": "warning"})
        self._create_notification()
        n = notification_queryset.first()
        self.assertEqual(n.level, "warning")

    @mock_notification_types
    def test_misc_notification_type_validation(self):
        with self.subTest("Registering with incomplete notification configuration."):
            with self.assertRaises(AssertionError):
                register_notification_type("test_type", dict())

        with self.subTest("Registering with improper notification type name"):
            with self.assertRaises(ImproperlyConfigured):
                register_notification_type(["test_type"], dict())

        with self.subTest("Registering with improper notification configuration"):
            with self.assertRaises(ImproperlyConfigured):
                register_notification_type("test_type", tuple())

        with self.subTest("Unregistering with improper notification type name"):
            with self.assertRaises(ImproperlyConfigured):
                unregister_notification_type(dict())

    @mock_notification_types
    def test_notification_type_message_template(self):
        message_template = {
            "level": "info",
            "verb": "message template verb",
            "verbose_name": "Message Template Type",
            "email_subject": "[{site.name}] Message Template Subject",
        }

        with self.subTest("Register type with non existent message template"):
            with self.assertRaises(TemplateDoesNotExist):
                message_template.update({"message_template": "wrong/path.md"})
                register_notification_type("message_template", message_template)

        with self.subTest("Registering type with message template"):
            message_template.update(
                {"message_template": "openwisp_notifications/default_message.md"}
            )
            register_notification_type("message_template", message_template)
            self.notification_options.update({"type": "message_template"})
            self._create_notification()
            n = notification_queryset.first()
            self.assertEqual(n.type, "message_template")
            self.assertEqual(n.email_subject, "[example.com] Message Template Subject")

        with self.subTest("Links in notification message"):
            url = _get_absolute_url(
                reverse(
                    f"admin:{self.users_app_label}_user_change", args=(self.admin.pk,)
                )
            )
            message = (
                "<p>info : None message template verb </p>\n"
                f'<p><a href="{url}">admin</a>'
                '\nreports\n<a href="#">None</a>\nmessage template verb.</p>'
            )
            self.assertEqual(n.message, message)

    @mock_notification_types
    def test_register_unregister_notification_type(self):
        from openwisp_notifications.types import NOTIFICATION_CHOICES

        test_type = {
            "verbose_name": "Test Notification Type",
            "level": "test",
            "verb": "testing",
            "message": "{notification.verb} initiated by {notification.actor} since {notification}",
            "email_subject": "[{site.name}] {notification.verb} reported by {notification.actor}",
        }

        with self.subTest("Registering new notification type"):
            register_notification_type("test_type", test_type)
            self.notification_options.update({"type": "test_type"})
            self._create_notification()
            n = notification_queryset.first()
            self.assertEqual(n.level, "test")
            self.assertEqual(n.verb, "testing")
            self.assertEqual(
                n.message,
                "<p>testing initiated by admin since 0\xa0minutes</p>",
            )
            self.assertEqual(n.email_subject, "[example.com] testing reported by admin")

        with self.subTest("Re-registering a notification type"):
            with self.assertRaises(ImproperlyConfigured):
                register_notification_type("test_type", test_type)

        with self.subTest("Check registration in NOTIFICATION_CHOICES"):
            notification_choice = NOTIFICATION_CHOICES[-1]
            self.assertTupleEqual(
                notification_choice, ("test_type", "Test Notification Type")
            )

        with self.subTest("Unregistering a notification type which does not exists"):
            with self.assertRaises(ImproperlyConfigured):
                unregister_notification_type("wrong type")

        with self.subTest("Unregistering a notification choice which does not exists"):
            with self.assertRaises(ImproperlyConfigured):
                _unregister_notification_choice("wrong type")

        with self.subTest('Unregistering "test_type"'):
            unregister_notification_type("test_type")
            with self.assertRaises(NotificationRenderException):
                get_notification_configuration("test_type")

        with self.subTest("Using non existing notification type for new notification"):
            with patch("logging.Logger.error") as mocked_logger:
                self._create_notification()
                mocked_logger.assert_called_once_with(
                    "Error encountered while creating notification: "
                    "No such Notification Type, test_type"
                )

        with self.subTest("Check unregistration in NOTIFICATION_CHOICES"):
            with self.assertRaises(ImproperlyConfigured):
                _unregister_notification_choice("test_type")

    def test_notification_email(self):
        self._create_operator()
        self.notification_options.update({"type": "default"})
        self._create_notification()
        self.assertEqual(len(mail.outbox), 1)

    @mock_notification_types
    def test_missing_relation_object(self):
        test_type = {
            "verbose_name": "Test Notification Type",
            "level": "info",
            "verb": "testing",
            "message": (
                "{notification.verb} initiated by"
                "[{notification.actor}]({notification.actor_link}) with"
                " [{notification.action_object}]({notification.action_link}) for"
                " [{notification.target}]({notification.target_link})."
            ),
            "email_subject": (
                "[{site.name}] {notification.verb} reported by"
                " {notification.actor} with {notification.action_object} for {notification.target}"
            ),
        }
        register_notification_type("test_type", test_type, models=[User])
        self.notification_options.pop("email_subject")
        self.notification_options.update({"type": "test_type"})

        with self.subTest("Missing target object after creation"):
            operator = self._get_operator()
            self.notification_options.update({"target": operator})
            self._create_notification()
            operator.delete()

            n_count = notification_queryset.count()
            self.assertEqual(n_count, 0)

        with self.subTest("Missing action object after creation"):
            operator = self._get_operator()
            self.notification_options.pop("target")
            self.notification_options.update({"action_object": operator})
            self._create_notification()
            operator.delete()

            n_count = notification_queryset.count()
            self.assertEqual(n_count, 0)

        with self.subTest("Missing actor object after creation"):
            operator = self._get_operator()
            self.notification_options.pop("action_object")
            self.notification_options.pop("url")
            self.notification_options.update({"sender": operator})
            self._create_notification()
            operator.delete()

            n_count = notification_queryset.count()
            self.assertEqual(n_count, 0)

    @mock_notification_types
    def test_notification_type_related_object_url(self):
        test_type = {
            "verbose_name": "Test Notification Type",
            "level": "test",
            "verb": "testing",
            "message": "{notification.verb} initiated by {notification.actor} since {notification}",
            "email_subject": "[{site.name}] {notification.verb} reported by {notification.actor}",
        }
        self.notification_options.update(
            {
                "type": "test_type",
                "sender": self._create_user(
                    username="actor", email="actor@example.com"
                ),
                "action_object": self._create_user(username="action-object"),
                "target": self._create_user(
                    username="target", email="target@example.com"
                ),
            }
        )
        # Creating notification will fail without registering
        # notification type here
        register_notification_type("test_type", test_type, models=[User])
        self._create_notification()

        with self.subTest("Test related object static URL"):
            # Update the notification type configuration
            unregister_notification_type("test_type")
            test_type["action_object_link"] = "https://action-object.example.com"
            test_type["actor_link"] = "https://actor.example.com"
            test_type["target_link"] = "https://target.example.com"
            register_notification_type("test_type", test_type, models=[User])

            notification = Notification.objects.first()
            self.assertEqual(
                notification.action_url, "https://action-object.example.com"
            )
            self.assertEqual(notification.actor_url, "https://actor.example.com")
            self.assertEqual(notification.target_url, "https://target.example.com")

        with self.subTest("Test related object callable URL"):
            # Update the notification type configuration
            unregister_notification_type("test_type")
            url_generator = "openwisp_notifications.tests.test_helpers.notification_related_object_url"
            test_type["action_object_link"] = url_generator
            test_type["actor_link"] = url_generator
            test_type["target_link"] = url_generator
            register_notification_type("test_type", test_type, models=[User])

            notification = Notification.objects.first()
            self.assertEqual(
                notification.action_url,
                "https://action-object.example.com/index#heading",
            )
            self.assertEqual(
                notification.actor_url, "https://actor.example.com/index#heading"
            )
            self.assertEqual(
                notification.target_url, "https://target.example.com/index#heading"
            )

    @capture_any_output()
    @mock_notification_types
    @patch("openwisp_notifications.tasks.delete_notification.delay")
    def test_notification_invalid_message_attribute(self, mocked_task):
        self.notification_options.update({"type": "test_type"})
        test_type = {
            "verbose_name": "Test Notification Type",
            "level": "info",
            "verb": "testing",
            "message": "{notification.actor.random}",
            "email_subject": "[{site.name}] {notification.actor.random}",
        }
        register_notification_type("test_type", test_type)
        self._create_notification()
        notification = notification_queryset.first()
        with self.assertRaises(NotificationRenderException) as context_manager:
            notification.message
        self.assertEqual(
            str(context_manager.exception),
            "Error encountered in rendering notification message",
        )
        with self.assertRaises(NotificationRenderException) as context_manager:
            notification.email_subject
        self.assertEqual(
            str(context_manager.exception),
            "Error encountered in generating notification email",
        )
        mocked_task.assert_called_with(notification_id=notification.id)

    def test_related_objects_database_query(self):
        operator = self._get_operator()
        self.notification_options.update(
            {"action_object": operator, "target": operator, "type": "default"}
        )
        n = self._create_notification().pop()[1][0]
        with self.assertNumQueries(1):
            # Accessing email_message should access all related objects
            # (actor, action_object, target) but only execute a single
            # query since these objects are cached when rendering
            # the notification, rather than executing separate queries for each one.
            n = notification_queryset.first()
            n.message

    @patch.object(app_settings, "CACHE_TIMEOUT", 0)
    def test_notification_cache_timeout(self):
        # Timeout=0 means value is not cached
        operator = self._get_operator()
        self.notification_options.update(
            {"action_object": operator, "target": operator}
        )
        self._create_notification()

        n = notification_queryset.first()
        with self.assertNumQueries(3):
            # Expect database query for each operation, nothing is cached
            self.assertEqual(n.actor, self.admin)
            self.assertEqual(n.action_object, operator)
            self.assertEqual(n.target, operator)

        # Test cache is not set
        self.assertIsNone(cache.get(Notification._cache_key(self.admin.pk)))
        self.assertIsNone(cache.get(Notification._cache_key(operator.pk)))

    def test_notification_target_content_type_deleted(self):
        operator = self._get_operator()
        self.notification_options.update(
            {"action_object": operator, "target": operator, "type": "default"}
        )
        self._create_notification()
        ContentType.objects.get_for_model(operator._meta.model).delete()
        ContentType.objects.clear_cache()
        # DoesNotExists exception should not be raised.
        operator.delete()

    def test_delete_old_notification(self):
        days_old = 91
        # Create notification with current timestamp
        self.notification_options.update({"type": "default"})
        self._create_notification()
        # Create notification with older timestamp
        self.notification_options.update(
            {"timestamp": timezone.now() - timedelta(days=days_old)}
        )
        self._create_notification()

        self.assertEqual(notification_queryset.count(), 2)
        tasks.delete_old_notifications.delay(days_old)
        self.assertEqual(notification_queryset.count(), 1)

    @mock_notification_types
    def test_unregistered_notification_type_related_notification(self):
        # Notifications related to notification type should
        # get deleted on unregistration of notification type
        self.notification_options.update({"type": "default"})
        unregister_notification_type("default")
        self.assertEqual(notification_queryset.count(), 0)

    @mock_notification_types
    def test_notification_type_email_notification_setting_true(self):
        test_type = {
            "verbose_name": "Test Notification Type",
            "level": "info",
            "verb": "testing",
            "message": "Test message",
            "email_subject": "Test Email Subject",
            "email_notification": True,
        }

        register_notification_type("test_type", test_type)
        target_obj = self._get_org_user()
        self.notification_options.update({"type": "test_type", "target": target_obj})

        with self.subTest("Test user email preference not defined"):
            self._create_notification()
            self.assertEqual(len(mail.outbox), 1)
            self.assertIsNotNone(mail.outbox.pop())

        with self.subTest('Test user email preference is "False"'):
            NotificationSetting.objects.filter(
                user=self.admin,
                type="test_type",
            ).update(email=False)
            self._create_notification()
            self.assertEqual(len(mail.outbox), 0)

    @mock_notification_types
    def test_notification_type_email_notification_setting_false(self):
        test_type = {
            "verbose_name": "Test Notification Type",
            "level": "info",
            "verb": "testing",
            "message": "Test message",
            "email_subject": "Test Email Subject",
            "email_notification": False,
        }

        register_notification_type("test_type", test_type)
        target_obj = self._get_org_user()
        self.notification_options.update({"type": "test_type", "target": target_obj})

        with self.subTest("Test user email preference not defined"):
            self._create_notification()
            self.assertEqual(len(mail.outbox), 0)

        with self.subTest('Test user email preference is "True"'):
            NotificationSetting.objects.filter(
                user=self.admin,
                type="test_type",
            ).update(email=True)
            self._create_notification()
            self.assertEqual(len(mail.outbox), 1)

    @mock_notification_types
    def test_notification_type_web_notification_setting_true(self):
        self.notification_options.update({"target": self._get_org_user()})
        test_type = {
            "verbose_name": "Test Notification Type",
            "level": "info",
            "verb": "testing",
            "message": "Test message",
            "email_subject": "Test Email Subject",
            "web_notification": True,
        }

        register_notification_type("test_type", test_type)
        self.notification_options.update({"type": "test_type"})

        with self.subTest("Test user web preference not defined"):
            self._create_notification()
            self.assertEqual(notification_queryset.delete()[0], 1)

        with self.subTest('Test user web preference is "False"'):
            NotificationSetting.objects.filter(
                user=self.admin, type="test_type"
            ).update(web=False)
            self._create_notification()
            self.assertEqual(notification_queryset.count(), 0)

    @mock_notification_types
    def test_notification_type_web_notification_setting_false(self):
        target_obj = self._get_org_user()
        self.notification_options.update({"target": target_obj})
        test_type = {
            "verbose_name": "Test Notification Type",
            "level": "info",
            "verb": "testing",
            "message": "Test message",
            "email_subject": "Test Email Subject",
            "web_notification": False,
        }

        register_notification_type("test_type", test_type)
        self.notification_options.update({"type": "test_type"})

        with self.subTest("Test user web preference not defined"):
            self._create_notification()
            self.assertEqual(notification_queryset.count(), 0)

        with self.subTest('Test user email preference is "True"'):
            unregister_notification_type("test_type")
            test_type.update({"web_notification": True})
            register_notification_type("test_type", test_type)
            self.notification_options.update({"type": "test_type"})

            notification_setting = NotificationSetting.objects.get(
                user=self.admin, type="test_type", organization=target_obj.organization
            )
            notification_setting.email = True
            notification_setting.save()
            notification_setting.refresh_from_db()
            self.assertTrue(notification_setting.email)

        with self.subTest('Test user web preference is "True"'):
            NotificationSetting.objects.filter(
                user=self.admin, type="test_type"
            ).update(web=True)
            self._create_notification()
            self.assertEqual(notification_queryset.count(), 1)

    @mock_notification_types
    def test_notification_type_email_web_notification_defaults(self):
        test_type = {
            "verbose_name": "Test Notification Type",
            "level": "info",
            "verb": "testing",
            "message": "Test message",
            "email_subject": "Test Email Subject",
        }
        register_notification_type("test_type", test_type)

        notification_type_config = get_notification_configuration("test_type")
        self.assertTrue(notification_type_config["web_notification"])
        self.assertTrue(notification_type_config["email_notification"])

    def test_inactive_user_not_receive_notification(self):
        target = self._get_org_user()
        self.notification_options.update({"target": target})

        with self.subTest("Test superuser is inactive"):
            self.admin.is_active = False
            self.admin.save()

            self._create_notification()
            self.assertEqual(notification_queryset.count(), 0)

        # Create org admin
        org_admin = self._create_org_user(user=self._get_operator(), is_admin=True)

        with self.subTest("Test superuser is inactive but org admin is active"):
            self._create_notification()
            self.assertEqual(notification_queryset.count(), 1)
            notification = notification_queryset.first()
            self.assertEqual(notification.recipient, org_admin.user)

        # Cleanup
        notification_queryset.delete()

        with self.subTest("Test both superuser and org admin is inactive"):
            org_admin.user.is_active = False
            org_admin.user.save()

            self._create_notification()
            self.assertEqual(notification_queryset.count(), 0)

        with self.subTest("Test superuser is active and org admin is inactive"):
            self.admin.is_active = True
            self.admin.save()

            self._create_notification()
            self.assertEqual(notification_queryset.count(), 1)
            notification = notification_queryset.first()
            self.assertEqual(notification.recipient, self.admin)

    def test_notification_received_only_by_org_admin(self):
        self.admin.delete()
        org_object = self._get_org_user()
        self.notification_options.update({"sender": org_object, "target": org_object})
        self._create_org_user(
            user=self._create_user(username="user", email="user@user.com")
        )
        org_admin = self._create_org_user(user=self._get_operator(), is_admin=True)

        self._create_notification()
        self.assertEqual(notification_queryset.count(), 1)
        notification = notification_queryset.first()
        self.assertEqual(notification.recipient, org_admin.user)

    @patch(
        "openwisp_notifications.tasks.ns_register_unregister_notification_type.delay",
        side_effect=OperationalError,
    )
    @patch("logging.Logger.warning")
    def test_post_migrate_handler_celery_broker_unreachable(self, mocked_logger, *args):
        post_migrate.send(
            sender=NotificationAppConfig, app_config=NotificationAppConfig
        )
        mocked_logger.assert_called_once()

    @mock_notification_types
    @patch.object(post_migrate, "receivers", [])
    @patch(
        "openwisp_notifications.tasks.ns_register_unregister_notification_type.delay",
    )
    def test_post_migrate_populate_notification_settings(self, mocked_task, *args):
        with patch.object(app_settings, "POPULATE_PREFERENCES_ON_MIGRATE", False):
            NotificationAppConfig.ready()
            post_migrate.send(
                sender=NotificationAppConfig, app_config=NotificationAppConfig
            )
            mocked_task.assert_not_called()
        with patch.object(app_settings, "POPULATE_PREFERENCES_ON_MIGRATE", True):
            NotificationAppConfig.ready()
            post_migrate.send(
                sender=NotificationAppConfig, app_config=NotificationAppConfig
            )
            mocked_task.assert_called_once()

    @patch("openwisp_notifications.types.NOTIFICATION_ASSOCIATED_MODELS", set())
    @patch("openwisp_notifications.tasks.delete_obsolete_objects.delay")
    def test_delete_obsolete_tasks(self, mocked_task, *args):
        user = self._create_user()
        user.delete()
        mocked_task.assert_not_called()

    def test_email_notif_without_notif_setting(self):
        target_obj = self._get_org_user()
        data = dict(
            email_subject="Test Email subject", url="https://localhost:8000/admin"
        )
        self.admin.notificationsetting_set.all().delete()
        Notification.objects.create(
            actor=self.admin,
            recipient=self.admin,
            description="Test Notification Description",
            verb="Test Notification",
            action_object=target_obj,
            target=target_obj,
            data=data,
            type="default",
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_notification_for_unverified_email(self):
        EmailAddress.objects.filter(user=self.admin).update(verified=False)
        self._create_notification()
        # we don't send emails to unverified email addresses
        self.assertEqual(len(mail.outbox), 0)

    @patch("openwisp_notifications.tasks.send_batched_email_notifications.apply_async")
    @patch("logging.Logger.error")
    @patch.object(utils, "send_email")
    def test_send_batched_email_notifications_no_instance_id(
        self, mocked_send_email, mocked_logger, *args
    ):
        # No cache key is set for "None", thus user lookup is not performed
        tasks.send_batched_email_notifications(None)
        mocked_logger.assert_not_called()
        mocked_send_email.assert_not_called()

        for _ in range(3):
            self._create_notification()
        admin_id = self.admin.id
        User.objects.filter(id=admin_id).delete()
        mocked_send_email.reset_mock()
        tasks.send_batched_email_notifications(admin_id)
        mocked_logger.assert_called_once_with(
            "Failed to send batched email notifications:"
            f" User with ID {admin_id} not found in the database."
        )
        mocked_send_email.assert_not_called()

    @patch("openwisp_notifications.tasks.send_batched_email_notifications.apply_async")
    def test_send_batched_email_notifications_single_notification(
        self, mock_send_email
    ):
        # The first notification will always be sent immediately
        self._create_notification()
        mail.outbox.clear()
        # There's only one notification in the batch, it should
        # not use summary of batched email.
        self._create_notification()
        # The task is mocked to prevent immediate execution in test environment.
        # In tests, Celery runs in EAGER mode which would execute tasks immediately,
        # preventing us from testing the batching behavior properly.
        tasks.send_batched_email_notifications(str(self.admin.id))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("1 unread notifications since", mail.outbox[0].body)

    @patch("openwisp_notifications.tasks.send_batched_email_notifications.apply_async")
    def test_batch_email_notification(self, mock_send_email):
        fixed_datetime = timezone.localtime(
            datetime(2024, 7, 26, 11, 40, tzinfo=dt_timezone.utc)
        )
        datetime_str = fixed_datetime.strftime("%B %-d, %Y, %-I:%M %p %Z")

        # Add multiple notifications with slightly different timestamps
        # to maintain consistent order in generated email text across test runs
        for _ in range(3):
            with freeze_time(fixed_datetime):
                # Create notifications with URL (from self.notification_options)
                self._create_notification()
            # Increment time for ordering consistency
            fixed_datetime += timedelta(microseconds=100)
        # Notification without URL
        self.notification_options.pop("url")
        with freeze_time(fixed_datetime):
            self._create_notification()
        fixed_datetime += timedelta(microseconds=100)
        # Notification with a type and target object
        self.notification_options.update(
            {"type": "default", "target": self._get_org_user()}
        )
        with freeze_time(fixed_datetime):
            read_notification = self._create_notification().pop()[1][0]
        notification_queryset.filter(id=read_notification.id).update(unread=False)

        fixed_datetime += timedelta(microseconds=100)
        with freeze_time(fixed_datetime):
            default = self._create_notification().pop()[1][0]

        # Check if only one mail is sent initially
        self.assertEqual(len(mail.outbox), 1)

        fixed_datetime += timedelta(microseconds=100)

        # Ensure the unsubscribe URL and the batch email notification
        # are generated with the same timestamp. This guarantees the
        # unsubscribe token in the email matches the one generated here,
        # since the token is timestamp-dependent.
        with freeze_time(fixed_datetime):
            # Call the task
            tasks.send_batched_email_notifications(self.admin.id)
            unsubscribe_url = utils.get_unsubscribe_url_for_user(self.admin)

        # Check if the rest of the notifications are sent in a batch
        self.assertEqual(len(mail.outbox), 2)
        email = mail.outbox[1]
        expected_subject = f"[example.com] 4 unread notifications since {datetime_str}"
        self.assertEqual(email.subject, expected_subject)
        self.assertEqual(
            email.body.strip(),
            _test_batch_email_notification_email_body.format(
                datetime_str=datetime_str,
                notification_id=default.id,
            ).strip(),
        )
        html_email = email.alternatives[0][0]
        self.assertInHTML(
            _test_batch_email_notification_email_html.format(
                datetime_str=datetime_str,
                notification_id=default.id,
                unsubscribe_url=unsubscribe_url,
            ),
            html_email,
        )

    @patch("openwisp_notifications.tasks.send_batched_email_notifications.apply_async")
    def test_batch_email_notification_with_call_to_action(self, mock_send_email):
        self.notification_options.update(
            {
                "message": "Notification title",
                "type": "default",
            }
        )
        display_limit = app_settings.EMAIL_BATCH_DISPLAY_LIMIT
        for _ in range(display_limit + 2):
            notify.send(recipient=self.admin, **self.notification_options)

        # Check if only one mail is sent initially
        self.assertEqual(len(mail.outbox), 1)

        # Call the task
        tasks.send_batched_email_notifications(self.admin.id)

        # Check if the rest of the notifications are sent in a batch
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(
            f"{display_limit} unread notifications since", mail.outbox[1].subject
        )
        self.assertIn("View all Notifications", mail.outbox[1].body)

    @patch.object(app_settings, "EMAIL_BATCH_INTERVAL", 0)
    def test_without_batch_email_notification(self):
        self.notification_options.update(
            {
                "message": "Notification title",
                "type": "default",
            }
        )
        for _ in range(3):
            notify.send(recipient=self.admin, **self.notification_options)

        self.assertEqual(len(mail.outbox), 3)

    @patch("openwisp_notifications.tasks.send_batched_email_notifications.apply_async")
    def test_batch_email_conditions(self, mock_send_email):
        """
        Batch email should be sent if the last email was
        sent less than EMAIL_BATCH_INTERVAL seconds ago.
        """
        now = timezone.now()
        past_time = now - timedelta(seconds=app_settings.EMAIL_BATCH_INTERVAL + 1)
        # Create the initial notification which sets the last email sent time
        with freeze_time(past_time):
            self._create_notification()
        self.assertEqual(len(mail.outbox), 1)
        mock_send_email.assert_not_called()
        self.assertEqual(
            Notification.get_user_batch_email_data(self.admin)[0], past_time
        )

        # Notification should not be batched because the last email was sent
        # more than EMAIL_BATCH_INTERVAL seconds ago.
        with freeze_time(now):
            self._create_notification()
        self.assertEqual(len(mail.outbox), 2)
        mock_send_email.assert_not_called()

        # Notification should be batched because the last email was sent
        # less than EMAIL_BATCH_INTERVAL seconds ago.
        with freeze_time(now + timedelta(seconds=1)):
            self._create_notification()
        self.assertEqual(len(mail.outbox), 2)
        mock_send_email.assert_called_once_with(
            (str(self.admin.id),),
            countdown=app_settings.EMAIL_BATCH_INTERVAL,
        )

        mock_send_email.reset_mock()
        # Subsequent notifications should not trigger a new batch
        with freeze_time(now + timedelta(seconds=2)):
            self._create_notification()
        self.assertEqual(len(mail.outbox), 2)
        mock_send_email.assert_not_called()
        self.assertEqual(len(Notification.get_user_batch_email_data(self.admin)[2]), 2)

        batch_end_time = now + timedelta(seconds=app_settings.EMAIL_BATCH_INTERVAL)
        # Subsequent notifications will be batched until the ETA of celery task
        with freeze_time(batch_end_time):
            self._create_notification()
        self.assertEqual(len(mail.outbox), 2)
        mock_send_email.assert_not_called()
        self.assertEqual(len(Notification.get_user_batch_email_data(self.admin)[2]), 3)

        # Celery task failed to execute (celery worker overloaded).
        # The email would be sent synchronously.
        with freeze_time(
            batch_end_time + timedelta(seconds=app_settings.EMAIL_BATCH_INTERVAL * 0.26)
        ):
            self._create_notification()
        mock_send_email.assert_not_called()
        self.assertEqual(len(mail.outbox), 3)
        self.assertIn(
            "[example.com] 4 unread notifications since",
            mail.outbox.pop().subject,
        )

    def test_that_the_notification_is_only_sent_once_to_the_user(self):
        first_org = self._create_org()
        first_org.organization_id = first_org.id
        second_org = self._create_org(name="second-org")
        second_org.organization_id = second_org.id
        OrganizationUser.objects.create(user=self.admin, organization=first_org)
        OrganizationUser.objects.create(user=self.admin, organization=second_org)
        self.notification_options.update(
            {
                "type": "default",
                "sender": first_org,
                "target": first_org,
            }
        )
        self._create_notification()
        self.assertEqual(notification_queryset.count(), 1)

    @patch("openwisp_notifications.tasks.send_batched_email_notifications.apply_async")
    def test_marking_notification_read_skips_batching(self, *args):
        """
        When a notification is read, it should not be included in the batch email.
        """
        self._create_notification()
        self.assertEqual(len(mail.outbox), 1)
        # Second notification will schedule a batch summary
        notification = self._create_notification().pop()[1][0]
        notification_queryset.filter(id=notification.id).update(unread=False)

        # Execute task to send batched email notifications
        tasks.send_batched_email_notifications(str(self.admin.id))
        # Batched email is not sent because the notification was marked as read
        self.assertEqual(len(mail.outbox), 1)
        # Task has cleared the batching
        self.assertEqual(Notification.get_user_batch_email_data(self.admin)[0], None)

        # Send email for a new notification
        self._create_notification()
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotEqual(Notification.get_user_batch_email_data(self.admin)[0], None)

    @mock_notification_types
    @patch("openwisp_notifications.tasks.send_batched_email_notifications.apply_async")
    def test_batch_notification_does_not_include_disabled_notification_type(
        self, *args
    ):
        register_notification_type("test", test_notification_type)
        target_obj = self._create_org_user()
        self.admin.notificationsetting_set.filter(type="test").update(email=False)
        self.notification_options.update({"type": "default", "target": target_obj})

        # Email for first notification is sent immediately.
        self._create_notification()
        self.assertEqual(len(mail.outbox), 1)

        # Batching of notifications begins
        for _ in range(2):
            self._create_notification()
        self.notification_options.update({"type": "test"})
        self._create_notification()
        tasks.send_batched_email_notifications(str(self.admin.id))
        self.assertEqual(len(mail.outbox), 2)
        email = mail.outbox.pop()
        # Batch should not contain "test" notification type
        self.assertIn("[example.com] 2 unread notifications since", email.subject)
        self.assertNotIn("testing initiated by admin", email.body)

    def test_email_unsubscribe_token(self):
        token = email_token_generator.make_token(self.admin)

        with self.subTest("Valid token for the user"):
            is_valid = email_token_generator.check_token(self.admin, token)
            self.assertTrue(is_valid)

        with self.subTest("Token used with a different user"):
            test_user = self._create_user(username="test")
            is_valid = email_token_generator.check_token(test_user, token)
            self.assertFalse(is_valid)

        with self.subTest("Token invalidated after password change"):
            self.admin.set_password("new_password")
            self.admin.save()
            is_valid = email_token_generator.check_token(self.admin, token)
            self.assertFalse(is_valid)

    def test_email_unsubscribe_view(self):
        unsubscribe_link_generated = get_unsubscribe_url_for_user(self.admin, False)
        token = unsubscribe_link_generated.split("?token=")[1]
        local_unsubscribe_url = reverse("notifications:unsubscribe")
        unsubscribe_url = f"{local_unsubscribe_url}?token={token}"

        with self.subTest("Test GET request with valid token"):
            response = self.client.get(unsubscribe_url)
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test POST request with valid token"):
            response = self.client.post(unsubscribe_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["message"], "Successfully unsubscribed")

        with self.subTest("Test GET request with invalid token"):
            response = self.client.get(f"{local_unsubscribe_url}?token=invalid_token")
            self.assertContains(response, "Invalid or Expired Link")
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test POST request with invalid token"):
            response = self.client.post(f"{local_unsubscribe_url}?token=invalid_token")
            self.assertEqual(response.status_code, 400)

        with self.subTest("Test GET request with invalid user"):
            tester = self._create_user(username="tester")
            tester_link_generated = get_unsubscribe_url_for_user(tester)
            token = tester_link_generated.split("?token=")[1]
            tester_unsubscribe_url = f"{local_unsubscribe_url}?token={token}"
            tester.delete()
            response = self.client.get(tester_unsubscribe_url)
            self.assertContains(response, "Invalid or Expired Link")
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test POST request with invalid user"):
            tester = self._create_user(username="tester")
            tester_link_generated = get_unsubscribe_url_for_user(tester)
            token = tester_link_generated.split("?token=")[1]
            tester_unsubscribe_url = f"{local_unsubscribe_url}?token={token}"
            tester.delete()
            response = self.client.post(tester_unsubscribe_url)
            self.assertEqual(response.status_code, 400)

        with self.subTest("Test GET request with no token"):
            response = self.client.get(local_unsubscribe_url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Invalid or Expired Link")
            self.assertFalse(response.context["valid"])

        with self.subTest("Test POST request with no token"):
            response = self.client.post(local_unsubscribe_url)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["message"], "No token provided")

        with self.subTest("Test POST request with empty JSON body"):
            response = self.client.post(
                unsubscribe_url, content_type="application/json"
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["message"], "Successfully unsubscribed")

        with self.subTest("Test POST request with subscribe=True in JSON"):
            response = self.client.post(
                unsubscribe_url,
                data=json.dumps({"subscribe": True}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["message"], "Successfully subscribed")

        with self.subTest("Test POST request with subscribe=False in JSON"):
            response = self.client.post(
                unsubscribe_url,
                data=json.dumps({"subscribe": False}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["message"], "Successfully unsubscribed")

        with self.subTest("Test POST request with invalid JSON"):
            invalid_json = "{'data: invalid}"
            response = self.client.post(
                unsubscribe_url,
                data=invalid_json,
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["message"], "Invalid JSON data")

    def test_notification_preference_page(self):
        preference_page = "notifications:user_notification_preference"
        tester = self._create_user(username="tester")

        with self.subTest("Test user is not authenticated"):
            response = self.client.get(reverse(preference_page, args=(self.admin.pk,)))
            self.assertEqual(response.status_code, 302)

        with self.subTest("Test with same user"):
            self.client.force_login(self.admin)
            response = self.client.get(reverse("notifications:notification_preference"))
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test user is authenticated"):
            self.client.force_login(self.admin)
            response = self.client.get(reverse(preference_page, args=(self.admin.pk,)))
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test user is authenticated but not superuser"):
            self.client.force_login(tester)
            response = self.client.get(reverse(preference_page, args=(self.admin.pk,)))
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test user is authenticated and superuser"):
            self.client.force_login(self.admin)
            response = self.client.get(reverse(preference_page, args=(tester.pk,)))
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test invalid user ID"):
            response = self.client.get(reverse(preference_page, args=(uuid4(),)))
            self.assertEqual(response.status_code, 404)


class TestTransactionNotifications(TestOrganizationMixin, TransactionTestCase):
    def setUp(self):
        self.admin = self._create_admin()
        self.notification_options = dict(
            sender=self.admin,
            description="Test Notification",
            level="info",
            verb="Test Notification",
            email_subject="Test Email subject",
            url="https://localhost:8000/admin",
        )

    def _create_notification(self):
        return notify.send(**self.notification_options)

    def test_notification_cache_update(self):
        operator = self._get_operator()
        register_notification_cache_update(
            User, post_save, "operator_name_changed_invalidation"
        )
        self.notification_options.update(
            {"action_object": operator, "target": operator, "type": "default"}
        )
        self._create_notification()
        content_type = ContentType.objects.get_for_model(operator._meta.model)
        cache_key = Notification._cache_key(content_type.id, operator.id)
        operator_cache = cache.get(cache_key, None)
        self.assertEqual(operator_cache.username, operator.username)
        operator.username = "new operator name"
        operator.save()
        notification = Notification.objects.get(target_content_type=content_type)
        cache_key = Notification._cache_key(content_type.id, operator.id)
        self._create_notification()
        operator_cache = cache.get(cache_key, None)
        self.assertEqual(notification.target.username, "new operator name")
        # Done for populating cache
        self.assertEqual(operator_cache.username, "new operator name")

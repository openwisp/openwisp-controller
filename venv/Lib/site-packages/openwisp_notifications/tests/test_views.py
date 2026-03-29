import logging

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from openwisp_notifications.swapper import load_model

User = get_user_model()

NotificationSetting = load_model("NotificationSetting")


class TestResendVerificationEmailView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.url = reverse("notifications:resend_verification_email")
        self.logger = logging.getLogger("openwisp_notifications.views")

    def test_unverified_primary_email_sends_email(self):
        email_address = EmailAddress.objects.get(user=self.user, primary=True)
        email_address.verified = False
        email_address.save()
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("admin:index"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(
            str(messages[0]), f"Confirmation email sent to {self.user.email}."
        )

    def test_auto_create_email_address(self):
        EmailAddress.objects.filter(user=self.user).delete()
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)
        email_address = EmailAddress.objects.get(user=self.user)
        self.assertRedirects(response, reverse("admin:index"))
        self.assertTrue(email_address.primary)
        self.assertFalse(email_address.verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_last_non_primary_email_used(self):
        EmailAddress.objects.filter(user=self.user, primary=True).delete()
        EmailAddress.objects.create(
            user=self.user, email="alt1@example.com", primary=False, verified=False
        )
        last_email = EmailAddress.objects.create(
            user=self.user, email="alt2@example.com", primary=False, verified=False
        )
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("admin:index"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [last_email.email])

    def test_redirect_with_next_param(self):
        safe_path = "/admin/safe-page/"
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(f"{self.url}?next={safe_path}")
        self.assertRedirects(response, safe_path, fetch_redirect_response=False)

    def test_log_unsafe_redirect_attempt(self):
        unsafe_url = "http://evil.com/admin"
        self.client.login(username="testuser", password="testpass123")
        with self.assertLogs(logger=self.logger, level="WARNING") as log:
            response = self.client.get(f"{self.url}?next={unsafe_url}")
            self.assertRedirects(response, reverse("admin:index"))
        self.assertIn("Unsafe redirect attempted", log.output[0])

    def test_verified_email_shows_info(self):
        email_address = EmailAddress.objects.get(user=self.user, primary=True)
        email_address.verified = True
        email_address.save()
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("admin:index"))
        self.assertEqual(len(mail.outbox), 0)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(str(messages[0]), "Your email is already verified.")

    def test_no_email_address_shows_message(self):
        EmailAddress.objects.filter(user=self.user).delete()
        self.user.email = ""
        self.user.save()
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("admin:index"))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(str(messages[0]), "No email address found for your account.")


class TestCheckEmailVerification(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="adminuser",
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
        )
        EmailAddress.objects.filter(user=self.user).delete()
        EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            primary=True,
            verified=False,
        )
        NotificationSetting.objects.update_or_create(
            user=self.user,
            type="default",
            defaults={"email": True, "web": True},
        )

    def test_warning_on_admin_login(self):
        login_url = reverse("admin:login")
        response = self.client.post(
            login_url,
            {
                "username": "adminuser",
                "password": "adminpass123",
                "next": reverse("admin:index"),
            },
            follow=True,
        )
        # Check for the warning message
        messages_list = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages_list), 1)
        message = str(messages_list[0])
        self.assertIn(
            "Email notifications are enabled, but emails cannot be sent", message
        )
        self.assertIn("verify your email address", message)
        expected_url = reverse("notifications:resend_verification_email")
        self.assertIn(expected_url, message)

    def test_email_notifications_disabled_no_warning(self):
        NotificationSetting.objects.update_or_create(
            user=self.user, type="default", defaults={"email": False, "web": True}
        )
        self.assertFalse(NotificationSetting.email_notifications_enabled(self.user))
        login_url = reverse("admin:login")
        response = self.client.post(
            login_url,
            {
                "username": "adminuser",
                "password": "adminpass123",
                "next": reverse("admin:index"),
            },
            follow=True,
        )
        messages_list = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages_list), 0)

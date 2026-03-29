from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.template import TemplateDoesNotExist
from django.test import TestCase
from django.urls import reverse

from ..accounts.adapter import EmailAdapter
from .utils import TestOrganizationMixin

User = get_user_model()


class TestEmailAdapter(TestOrganizationMixin, TestCase):
    def test_template_not_present(self):
        email = "test@tester.com"
        template_prefix = "some_random_name"

        with self.assertRaises(TemplateDoesNotExist):
            EmailAdapter.send_mail(self, template_prefix, email, {})

    @mock.patch("openwisp_users.accounts.adapter.send_email")
    def test_assertion_not_raised_when_html_template_missing(self, mail_func):
        self._create_user()
        queryset = User.objects.filter(username="tester")
        self.assertEqual(queryset.count(), 1)
        params = {"email": "test@tester.com"}
        self.client.post(reverse("account_reset_password"), params, follow=True)
        send_mail_calls = mail_func.call_args_list
        send_mail_arguments = send_mail_calls[0][0]
        self.assertEqual(send_mail_arguments[0], "[example.com] Password Reset Email")
        self.assertEqual(send_mail_arguments[2], "")

    def test_password_reset_email_sent(self):
        self._create_user()
        queryset = User.objects.filter(username="tester")
        self.assertEqual(queryset.count(), 1)
        params = {"email": "test@tester.com"}
        self.client.post(reverse("account_reset_password"), params, follow=True)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox.pop()
        self.assertFalse(email.alternatives)
        self.assertIn("Password Reset Email", email.subject)
        self.assertIn("Click the link below to reset your password", email.body)

    def test_password_reset_includes_site_name(self):
        self._create_user()
        params = {"email": "test@tester.com"}
        self.client.post(reverse("account_reset_password"), params, follow=True)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        # plain text body should contain example.com from site name
        self.assertIn("example.com", email.body)
        # if there is an HTML alternative, check it too
        if email.alternatives:
            html = email.alternatives[0][0]
            self.assertIn("example.com", html)

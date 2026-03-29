import contextlib
import re
import smtplib
import uuid
from unittest.mock import patch

import django
from django.contrib import admin as django_admin
from django.contrib.auth import REDIRECT_FIELD_NAME, get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS
from django.template.defaultfilters import date
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now, timedelta
from swapper import load_model

from openwisp_utils.tests import AdminActionPermTestMixin, capture_any_output

from .. import settings as app_settings
from ..admin import OrganizationOwnerAdmin
from ..apps import logger as apps_logger
from ..multitenancy import MultitenantAdminMixin
from .utils import (
    TestMultitenantAdminMixin,
    TestOrganizationMixin,
    TestUserAdditionalFieldsMixin,
)

Organization = load_model("openwisp_users", "Organization")
OrganizationUser = load_model("openwisp_users", "OrganizationUser")
OrganizationOwner = load_model("openwisp_users", "OrganizationOwner")
User = get_user_model()
Group = load_model("openwisp_users", "Group")


class TestUsersAdmin(
    AdminActionPermTestMixin,
    TestOrganizationMixin,
    TestUserAdditionalFieldsMixin,
    TestCase,
):
    """test admin site"""

    app_label = "openwisp_users"
    is_integration_test = False

    def assertNumQueries(self, num, using=DEFAULT_DB_ALIAS, func=None, *args, **kwargs):
        # in integration tests the amount of queries
        # is different so we skip this test for now
        if self.is_integration_test:
            return contextlib.suppress()
        else:
            return super().assertNumQueries(num, func=None, *args, **kwargs)

    def _get_org_edit_form_inline_params(self, user, organization):
        """
        This function is created to be overridden
        when the user extends openwisp-users
        and adds inline forms in the Organization model.
        """
        return dict()

    def _get_user_edit_form_inline_params(self, user, organization):
        """
        This function is created to be overridden
        when the user extends openwisp-users
        and adds inline forms in the User model
        """
        return dict()

    @property
    def add_user_inline_params(self):
        return {
            "emailaddress_set-TOTAL_FORMS": 0,
            "emailaddress_set-INITIAL_FORMS": 0,
            "emailaddress_set-MIN_NUM_FORMS": 0,
            "emailaddress_set-MAX_NUM_FORMS": 0,
            f"{self.app_label}_organizationuser-TOTAL_FORMS": 0,
            f"{self.app_label}_organizationuser-INITIAL_FORMS": 0,
            f"{self.app_label}_organizationuser-MIN_NUM_FORMS": 0,
            f"{self.app_label}_organizationuser-MAX_NUM_FORMS": 0,
        }

    def test_admin_add_user_auto_email(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        params = dict(
            username="testadd",
            email="test@testadd.com",
            password1="tester",
            password2="tester",
        )
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        self.client.post(reverse(f"admin:{self.app_label}_user_add"), params)
        queryset = User.objects.filter(username="testadd")
        self.assertEqual(queryset.count(), 1)
        user = queryset.first()
        self.assertEqual(user.emailaddress_set.count(), 1)
        emailaddress = user.emailaddress_set.first()
        self.assertEqual(emailaddress.email, "test@testadd.com")
        self.assertEqual(len(mail.outbox), 1)

        with self.subTest("Test HTML Template used for Signup Mail"):
            email = mail.outbox.pop()
            self.assertTrue(email.alternatives)
            self.assertIn("<b>testadd</b>", email.alternatives[0][0])
            self.assertIn(
                "To confirm this is correct, please click on the button below",
                email.alternatives[0][0],
            )

    def test_admin_add_user_empty_email(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        params = dict(
            username="testadd", email="", password1="tester", password2="tester"
        )
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        response = self.client.post(reverse(f"admin:{self.app_label}_user_add"), params)
        queryset = User.objects.filter(username="testadd")
        self.assertEqual(queryset.count(), 0)
        self.assertContains(response, "errors field-email")
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_change_user_auto_email(self):
        admin = self._create_admin()
        self._create_org_user(user=admin)
        self.client.force_login(admin)
        user = self._create_user(email="old@mail.com", username="changemailtest")
        params = user.__dict__
        params["email"] = "new@mail.com"
        params.pop("phone_number")
        params.pop("password", None)
        params.pop("_password", None)
        params.pop("last_login")
        params.pop("password_updated")
        params = self._additional_params_pop(params)
        # inline emails
        params.update(self.add_user_inline_params)
        params.update(
            {
                "emailaddress_set-TOTAL_FORMS": 1,
                "emailaddress_set-INITIAL_FORMS": 1,
                "emailaddress_set-0-verified": True,
                "emailaddress_set-0-primary": True,
                "emailaddress_set-0-id": user.emailaddress_set.first().id,
                "emailaddress_set-0-user": user.id,
            }
        )
        params.update(self._get_user_edit_form_inline_params(user, self._get_org()))
        response = self.client.post(
            reverse(f"admin:{self.app_label}_user_change", args=[user.pk]),
            params,
            follow=True,
        )
        self.assertNotContains(response, "Please correct the error below.")
        user = User.objects.get(username="changemailtest")
        email_set = user.emailaddress_set
        self.assertEqual(email_set.count(), 2)
        self.assertEqual(email_set.filter(email="new@mail.com").count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_admin_change_user_email_empty(self):
        admin = self._create_admin(email="")
        self._create_org_user(user=admin)
        self.client.force_login(admin)
        params = dict(
            username="testchange",
            email="",
            first_name="",
            last_name="",
            bio="",
            url="",
            company="",
            location="",
        )
        params.update(self.add_user_inline_params)
        params.update(self._get_user_edit_form_inline_params(admin, self._get_org()))
        response = self.client.post(
            reverse(f"admin:{self.app_label}_user_change", args=[admin.pk]), params
        )
        queryset = User.objects.filter(username="testchange")
        self.assertEqual(queryset.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(response, "errors field-email")

    def test_admin_change_user_page_get_invalid_UUID(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        with self.subTest("Test for wrong identifier"):
            response = self.client.get(
                reverse(f"admin:{self.app_label}_user_change", args=["WRONG"]),
                follow=True,
            )
            content = "User with ID “WRONG” doesn’t exist. Perhaps it was deleted?"
            self.assertContains(response, content, status_code=200)
        with self.subTest("Test for non-existing user"):
            id = uuid.uuid4()
            response = self.client.get(
                reverse(
                    f"admin:{self.app_label}_user_change",
                    args=[id],
                ),
                follow=True,
            )
            content = f"User with ID “{id}” doesn’t exist. Perhaps it was deleted?"
            self.assertContains(response, content, status_code=200)

    def test_admin_change_user_password_updated(self):
        admin = self._create_admin()
        # User.objects.create_user does not execute User.set_password
        # which is required for setting User.password_updated field
        admin.set_password("tester")
        admin.save()
        self.client.force_login(admin)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_user_change", args=[admin.pk]),
        )
        self.assertContains(
            response,
            (
                "<label>Password updated:</label>\n\n"
                f'<div class="readonly">{date(now())}</div>'
            ),
            html=True,
        )

    def test_admin_change_user_reuse_password(self):
        admin = self._create_admin(password="tester")
        self.client.force_login(admin)
        path = reverse("admin:auth_user_password_change", args=[admin.pk])
        data = {"password1": "tester", "password2": "tester"}
        with override_settings(
            AUTH_PASSWORD_VALIDATORS=[
                {
                    "NAME": "openwisp_users.password_validation.PasswordReuseValidator",
                },
            ]
        ):
            response = self.client.post(
                path,
                data=data,
                follow=True,
            )
            self.assertNotContains(
                response, '<li class="success">Password changed successfully.</li>'
            )
            self.assertContains(
                response,
                (
                    '<ul class="errorlist"{}><li>'
                    "You cannot re-use your current password. "
                    "Enter a new password.</li></ul>"
                ).format(
                    ' id="id_password2_error"' if django.VERSION >= (5, 2) else ""
                ),
            )
        with override_settings(AUTH_PASSWORD_VALIDATORS=[]):
            response = self.client.post(
                path,
                data=data,
                follow=True,
            )
            self.assertNotContains(
                response,
                (
                    '<ul class="errorlist"><li>'
                    "You cannot re-use your current password. "
                    "Enter a new password.</li></ul>"
                ),
            )
            self.assertContains(
                response, '<li class="success">Password changed successfully.</li>'
            )

    def test_organization_view_on_site(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        org = self._create_org()
        response = self.client.get(
            reverse(f"admin:{self.app_label}_organization_change", args=[org.pk])
        )
        self.assertNotContains(response, "viewsitelink")

    def test_organization_user_view_on_site(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        org = self._create_org()
        ou = self._create_org_user(organization=org, user=admin)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_organizationuser_change", args=[ou.pk])
        )
        self.assertNotContains(response, "viewsitelink")

    def test_admin_change_user_is_superuser_editable(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_user_change", args=[admin.pk])
        )
        html = '<input type="checkbox" name="is_superuser"'
        self.assertContains(response, html)

    def test_admin_change_user_is_superuser_absent(self):
        operator = self._create_operator_with_user_permissions()
        options = {
            "organization": self._get_org(),
            "is_admin": True,
            "user": self._get_operator(),
        }
        self._create_org_user(**options)
        self.client.force_login(operator)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_user_change", args=[operator.pk])
        )
        html = (
            '<input type="checkbox" name="is_superuser" checked id="id_is_superuser">'
        )
        self.assertNotContains(response, html)

    def test_admin_change_user_permissions_editable(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_user_change", args=[admin.pk])
        )
        html = '<select name="user_permissions"'
        self.assertContains(response, html)

    def test_admin_change_non_superuser_readonly_fields(self):
        operator = self._create_operator_with_user_permissions()
        options = {
            "organization": self._get_org(),
            "is_admin": True,
            "user": self._get_operator(),
        }
        self._create_org_user(**options)
        self.client.force_login(operator)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_user_change", args=[operator.pk])
        )
        with self.subTest("User Permissions"):
            # regex to check if `<div class="readonly"> ... app_label </div>`
            # exists in the response
            html = f"v((?!</div>).)*({self.app_label})"
            self.assertTrue(
                re.search(
                    html,
                    str(response.content),
                )
            )
        with self.subTest("Organization User Inline"):
            html = 'class="readonly"><img src="/static/admin/img/icon'
            self.assertContains(response, html)

    def test_org_manager_privilege_escalation(self):
        operator = self._create_operator_with_user_permissions()
        options = {
            "organization": self._get_org(),
            "is_admin": True,
            "user": self._get_operator(),
        }
        self._create_org_user(**options)
        self.client.force_login(operator)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_user_change", args=[operator.pk])
        )
        self.assertNotContains(response, "superuser")
        self.assertNotContains(response, "id_user_permissions_from")

    def test_admin_changelist_user_superusers_hidden(self):
        self._create_admin()
        operator = self._create_operator_with_user_permissions()
        self.client.force_login(operator)
        response = self.client.get(reverse(f"admin:{self.app_label}_user_changelist"))
        self.assertNotContains(response, "admin</a>")

    def test_admin_changelist_operator_org_users_visible(self):
        # Check with operator in same organization and is_admin
        self._create_org_user()
        operator = self._create_operator_with_user_permissions()
        options = {"organization": self._get_org(), "is_admin": True, "user": operator}
        self._create_org_user(**options)
        self.client.force_login(operator)
        response = self.client.get(reverse(f"admin:{self.app_label}_user_changelist"))
        self.assertContains(response, "tester</a>")
        self.assertContains(response, "operator</a>")

    def test_operator_changelist_superuser_column_hidden(self):
        operator = self._create_operator_with_user_permissions()
        options = {"organization": self._get_org(), "is_admin": True, "user": operator}
        self._create_org_user(**options)
        self.client.force_login(operator)
        response = self.client.get(reverse(f"admin:{self.app_label}_user_changelist"))
        self.assertNotContains(response, "Superuser status</a>")

    def test_operator_organization_member(self):
        org1 = self._create_org(name="operator-org1")
        org2 = self._create_org(name="operator-org2")
        operator = self._create_operator_with_user_permissions()
        options1 = {"organization": org1, "is_admin": True, "user": operator}
        options2 = {"organization": org2, "is_admin": False, "user": operator}
        self._create_org_user(**options1)
        self._create_org_user(**options2)
        self.client.force_login(operator)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_user_change", args=[operator.pk])
        )
        self.assertContains(response, "selected>operator-org1</option>")
        self.assertNotContains(response, "selected>operator-org2</option>")

    # the autocomplete fields are removed only in this
    # test to make testing multitenancy simpler
    @patch("openwisp_users.admin.OrganizationUserInline.autocomplete_fields", [])
    def test_operator_can_see_organization_add_user(self, *args):
        org1 = self._create_org(name="operator-org1")
        org2 = self._create_org(name="operator-org2")
        operator = self._create_operator_with_user_permissions()
        org_permissions = Permission.objects.filter(
            codename__endswith="organization_user"
        )
        operator.user_permissions.add(*org_permissions)
        options1 = {"organization": org1, "is_admin": True, "user": operator}
        options2 = {"organization": org2, "is_admin": False, "user": operator}
        self._create_org_user(**options1)
        self._create_org_user(**options2)
        self.client.force_login(operator)
        response = self.client.get(reverse(f"admin:{self.app_label}_user_add"))
        self.assertContains(response, "operator-org1</option>")
        self.assertNotContains(response, "operator-org2</option>")

    def test_operator_change_organization(self):
        org1 = self._create_org(name="test-org1")
        org2 = self._create_org(name="test-org2")
        default_org = Organization.objects.get(name="default")
        operator = self._create_operator()
        org_permissions = Permission.objects.filter(
            codename__endswith="change_organization"
        )
        operator.user_permissions.add(*org_permissions)
        options1 = {"organization": org1, "is_admin": True, "user": operator}
        options2 = {"organization": org2, "is_admin": False, "user": operator}
        self._create_org_user(**options1)
        self._create_org_user(**options2)
        self.client.force_login(operator)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_organization_change", args=[org1.pk])
        )
        self.assertContains(
            response, '<input type="text" name="name" value="{0}"'.format(org1.name)
        )
        response = self.client.get(
            reverse(
                f"admin:{self.app_label}_organization_change", args=[default_org.pk]
            )
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_organization_change", args=[org2.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_operator_change_org_is_admin(self):
        org1 = self._create_org(name="test-org1")
        org2 = self._create_org(name="test-org2")
        operator = self._create_operator_with_user_permissions()
        org_permissions = Permission.objects.filter(
            codename__endswith="change_organization"
        )
        operator.user_permissions.add(*org_permissions)
        options1 = {"organization": org1, "is_admin": True, "user": operator}
        options2 = {"organization": org2, "is_admin": False, "user": operator}
        org_user1 = self._create_org_user(**options1)
        org_user2 = self._create_org_user(**options2)
        self.client.force_login(operator)
        response = self.client.get(
            reverse(
                f"admin:{self.app_label}_organizationuser_change", args=[org_user1.pk]
            )
        )
        self.assertNotContains(
            response,
            '<input type="checkbox" name="is_admin" id="id_is_admin">'
            '<label class="vCheckboxLabel" for="id_is_admin">Is admin'
            "</label>",
        )
        response = self.client.get(
            reverse(
                f"admin:{self.app_label}_organizationuser_change", args=[org_user2.pk]
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_admin_operator_delete_org_user(self):
        org1 = self._create_org(name="test-org1")
        org2 = self._create_org(name="test-org2")
        operator = self._create_operator_with_user_permissions()
        org_permissions = Permission.objects.filter(
            codename__endswith="organization_user"
        )
        operator.user_permissions.add(*org_permissions)
        options1 = {"organization": org1, "is_admin": True, "user": operator}
        options2 = {"organization": org2, "is_admin": False, "user": operator}
        org_user1 = self._create_org_user(**options1)
        org_user2 = self._create_org_user(**options2)
        self.client.force_login(operator)
        response = self.client.get(
            reverse(
                f"admin:{self.app_label}_organizationuser_change", args=[org_user1.pk]
            )
        )
        self.assertContains(
            response,
            'class="deletelink-box">'
            f'<a href="/admin/{self.app_label}/organizationuser/{org_user1.pk}'
            '/delete/" class="deletelink">Delete',
        )
        response = self.client.get(
            reverse(
                f"admin:{self.app_label}_organizationuser_change", args=[org_user2.pk]
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_admin_changelist_superuser_column_visible(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse(f"admin:{self.app_label}_user_changelist"))
        self.assertContains(response, "Superuser status</a>")

    def test_admin_operator_change_superuser_forbidden(self):
        admin = self._create_admin()
        operator = self._create_operator_with_user_permissions()
        options = {
            "organization": self._get_org(),
            "is_admin": True,
            "user": self._get_operator(),
        }
        self._create_org_user(**options)
        self.client.force_login(operator)
        response = self.client.get(
            reverse(f"admin:{self.app_label}_user_change", args=[operator.pk])
        )
        self.assertEqual(response.status_code, 200)
        # operator trying to acess change form of superuser gets redirected
        response = self.client.get(
            reverse(f"admin:{self.app_label}_user_change", args=[admin.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_new_user_email_exists(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        params = dict(
            username="testadd",
            email="test@testadd.com",
            password1="tester",
            password2="tester",
        )
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        self.client.post(reverse(f"admin:{self.app_label}_user_add"), params)
        res = self.client.post(reverse(f"admin:{self.app_label}_user_add"), params)
        self.assertContains(
            res, "<li>User with this Email address already exists.</li>"
        )

    def test_create_user_existing_mail_different_case(self):
        self._create_user(username="user1", email="user@example.com")
        admin = self._create_admin()
        self.client.force_login(admin)
        params = dict(
            username="testadd",
            email="USER@example.com",
            password1="tester",
            password2="tester",
        )
        params.update(self.add_user_inline_params)
        res = self.client.post(reverse(f"admin:{self.app_label}_user_add"), params)
        content = "<li>User with this Email address already exists.</li>"
        self.assertContains(res, content, status_code=200)

    def test_update_user_no_validation_error(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        user = self._create_user(email="user@example.com", username="user1")
        params = user.__dict__
        params["username"] = "user2"
        params.pop("last_login")
        params.pop("password_updated")
        params.pop("phone_number")
        params.pop("password", None)
        params.pop("_password", None)
        params = self._additional_params_pop(params)
        params.update(self.add_user_inline_params)
        params.update(
            {
                "emailaddress_set-TOTAL_FORMS": 1,
                "emailaddress_set-INITIAL_FORMS": 1,
                "emailaddress_set-0-verified": True,
                "emailaddress_set-0-primary": True,
                "emailaddress_set-0-id": user.emailaddress_set.first().id,
                "emailaddress_set-0-user": user.id,
            }
        )
        params.update(self._get_user_edit_form_inline_params(user, self._get_org()))
        res = self.client.post(
            reverse(f"admin:{self.app_label}_user_change", args=[user.pk]),
            params,
            follow=True,
        )
        user.refresh_from_db()
        self.assertNotIn(
            "<li>User with this Email address already exists.</li>",
            res.content.decode(),
        )
        self.assertEqual(user.username, "user2")

    def test_edit_user_email_exists(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        self._get_org_user()
        user = self._create_user(email="asd@asd.com", username="newTester")
        self._create_org_user(user=user)
        params = user.__dict__
        params["email"] = "test@tester.com"
        params.pop("phone_number")
        params.pop("password", None)
        params.pop("_password", None)
        params.pop("last_login")
        params.pop("password_updated")
        params = self._additional_params_pop(params)
        params.update(self.add_user_inline_params)
        params.update(
            {
                "emailaddress_set-TOTAL_FORMS": 1,
                "emailaddress_set-INITIAL_FORMS": 1,
                "emailaddress_set-0-verified": True,
                "emailaddress_set-0-primary": True,
                "emailaddress_set-0-id": user.emailaddress_set.first().id,
                "emailaddress_set-0-user": user.id,
            }
        )
        params.update(self._get_user_edit_form_inline_params(user, self._get_org()))
        res = self.client.post(
            reverse(f"admin:{self.app_label}_user_change", args=[user.pk]),
            params,
            follow=True,
        )
        self.assertContains(
            res, "<li>User with this Email address already exists.</li>"
        )

    def test_change_staff_without_group(self):
        self.client.force_login(self._get_admin())
        user = self._create_user(is_staff=True)
        self._create_org_user(user=user)
        params = user.__dict__
        params.pop("password", None)
        params.pop("_password", None)
        params.pop("last_login")
        params.pop("password_updated")
        params.pop("phone_number")
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        params.update(self._get_user_edit_form_inline_params(user, self._get_org()))
        path = reverse(f"admin:{self.app_label}_user_change", args=[user.pk])
        r = self.client.post(path, params, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(
            r, "A staff user must belong to a group, please select one."
        )
        user.refresh_from_db()
        self.assertEqual(user.groups.count(), 0)

    def test_change_staff_with_group(self):
        self.client.force_login(self._get_admin())
        user = self._create_operator()
        org = self._get_org()
        self._create_org_user(organization=org, user=user)
        group = Group.objects.get(name="Administrator")
        params = user.__dict__
        params["groups"] = str(group.pk)
        params.pop("phone_number")
        params.pop("password", None)
        params.pop("_password", None)
        params.pop("last_login")
        params.pop("password_updated")
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        params.update(self._get_user_edit_form_inline_params(user, org))
        path = reverse(f"admin:{self.app_label}_user_change", args=[user.pk])
        r = self.client.post(path, params, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Please correct the error below.")
        user.refresh_from_db()
        self.assertEqual(user.groups.count(), 1)
        self.assertEqual(user.groups.get(name="Administrator").pk, group.pk)

    def test_staff_cannot_edit_org_owner(self):
        user1 = self._create_user(
            username="user1", email="email1@mail.com", is_staff=True
        )
        user2 = self._create_user(
            username="user2", email="email2@mail.com", is_staff=True
        )
        org = self._get_org()
        org_user2 = self._create_org_user(user=user2, organization=org, is_admin=True)
        self._create_org_user(user=user1, organization=org, is_admin=True)
        group = Group.objects.filter(name="Administrator")
        user1.groups.set(group)
        user2.groups.set(group)
        self.client.force_login(user1)
        path = reverse(f"admin:{self.app_label}_user_change", args=[user2.pk])
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'class="readonly">{user2.username}')
        message = (
            "You do not have permission to edit or delete "
            "this user because they are owner of an organization."
        )
        self.assertContains(r, message)

        org_owner = OrganizationOwner.objects.get(organization_user=org_user2)
        org_owner.delete()
        path = reverse(f"admin:{self.app_label}_user_change", args=[user2.pk])
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, f'class="readonly">{user2.username}')

    def _test_change(self, options):
        user1 = None
        user2 = None
        group = Group.objects.get(name="Administrator")
        org = self._get_org()
        for key, user in options.items():
            u = self._create_user(**user.get("fields"))
            self._create_org_user(user=u, organization=org, is_admin=True)
            u.groups.add(group)
            if user1:
                user2 = u
                continue
            user1 = u
        if user1 and not user2:
            user2 = user1
        self.client.force_login(user1)
        params = user2.__dict__
        params["username"] = "newuser1"
        params["groups"] = str(group.pk)
        params.pop("phone_number")
        params.pop("password", None)
        params.pop("_password", None)
        params.pop("last_login")
        params.pop("password_updated")
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        params.update(self._get_user_edit_form_inline_params(user2, org))
        path = reverse(f"admin:{self.app_label}_user_change", args=[user2.pk])
        r = self.client.post(path, params, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Please correct the error below.")
        user2.refresh_from_db()
        self.assertEqual(user2.username, "newuser1")

    def test_staff_can_edit_staff(self):
        options = {
            "user1": {
                "fields": {
                    "username": "user1",
                    "email": "email1@mail.com",
                    "is_staff": True,
                },
                "is_owner": False,
            },
            "user2": {
                "fields": {
                    "username": "user2",
                    "email": "email2@mail.com",
                    "is_staff": True,
                },
                "is_owner": False,
            },
        }
        self._test_change(options)

    def test_org_owner_can_edit_staff(self):
        options = {
            "user1": {
                "fields": {
                    "username": "user1",
                    "email": "email1@mail.com",
                    "is_staff": True,
                },
                "is_owner": True,
            },
            "user2": {
                "fields": {
                    "username": "user2",
                    "email": "email2@mail.com",
                    "is_staff": True,
                },
                "is_owner": False,
            },
        }
        self._test_change(options)

    def test_org_owner_can_edit_org_owner(self):
        options = {
            "user1": {
                "fields": {
                    "username": "user1",
                    "email": "email1@mail.com",
                    "is_staff": True,
                },
                "is_owner": True,
            }
        }
        self._test_change(options)

    def test_staff_can_edit_itself(self):
        options = {
            "user1": {
                "fields": {
                    "username": "user1",
                    "email": "email1@mail.com",
                    "is_staff": True,
                },
                "is_owner": False,
            }
        }
        self._test_change(options)

    def test_admin_add_user_by_superuser(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        res = self.client.get(reverse(f"admin:{self.app_label}_user_add"))
        self.assertContains(res, "is_superuser")

    def test_admin_add_user_by_operator(self):
        operator = self._create_operator_with_user_permissions()
        self.client.force_login(operator)
        res = self.client.get(reverse(f"admin:{self.app_label}_user_add"))
        self.assertNotContains(res, "is_superuser")

    def test_admin_add_user_org_required(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        params = dict(
            username="testadd",
            email="test@testadd.com",
            password1="tester",
            password2="tester",
            is_staff=True,
            is_superuser=False,
        )
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        params.update(
            {
                f"{self.app_label}_organizationuser-TOTAL_FORMS": 1,
                f"{self.app_label}_organizationuser-INITIAL_FORMS": 0,
                f"{self.app_label}_organizationuser-MIN_NUM_FORMS": 0,
                f"{self.app_label}_organizationuser-MAX_NUM_FORMS": 1,
            }
        )
        res = self.client.post(reverse(f"admin:{self.app_label}_user_add"), params)
        queryset = User.objects.filter(username="testadd")
        self.assertEqual(queryset.count(), 0)
        self.assertContains(res, "errors field-organization")

    def test_admin_user_add_form(self):
        self.client.force_login(self._get_admin())
        r = self.client.get(reverse(f"admin:{self.app_label}_user_add"))
        self.assertContains(r, "first_name")
        self.assertContains(r, "last_name")
        self.assertContains(r, "phone_number")
        self.assertContains(r, "groups")

    def test_add_staff_without_group(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        org = self._get_org()
        params = dict(
            username="testadd",
            email="test@testadd.com",
            password1="tester",
            password2="tester",
            is_staff=True,
        )
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        params.update(
            {
                f"{self.app_label}_organizationuser-TOTAL_FORMS": 1,
                f"{self.app_label}_organizationuser-INITIAL_FORMS": 0,
                f"{self.app_label}_organizationuser-MIN_NUM_FORMS": 0,
                f"{self.app_label}_organizationuser-MAX_NUM_FORMS": 1,
                f"{self.app_label}_organizationuser-0-is_admin": "on",
                f"{self.app_label}_organizationuser-0-organization": str(org.pk),
            }
        )
        res = self.client.post(
            reverse(f"admin:{self.app_label}_user_add"), params, follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(
            res, "A staff user must belong to a group, please select one."
        )
        user = User.objects.filter(username="testadd")
        self.assertEqual(user.count(), 0)

    def test_add_staff_with_group(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        group = Group.objects.get(name="Administrator")
        org = self._get_org()
        params = dict(
            username="testadd",
            email="test@testadd.com",
            password1="tester",
            password2="tester",
            is_staff=True,
        )
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        params.update(
            {
                "groups": str(group.pk),
                f"{self.app_label}_organizationuser-TOTAL_FORMS": 1,
                f"{self.app_label}_organizationuser-INITIAL_FORMS": 0,
                f"{self.app_label}_organizationuser-MIN_NUM_FORMS": 0,
                f"{self.app_label}_organizationuser-MAX_NUM_FORMS": 1,
                f"{self.app_label}_organizationuser-0-is_admin": "on",
                f"{self.app_label}_organizationuser-0-organization": str(org.pk),
            }
        )
        res = self.client.post(
            reverse(f"admin:{self.app_label}_user_add"), params, follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, "Please correct the error below.")
        user = User.objects.filter(username="testadd")
        self.assertEqual(user.count(), 1)

    def test_add_user_fieldsets(self):
        self.client.force_login(self._get_admin())
        r = self.client.get(reverse(f"admin:{self.app_label}_user_add"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Permissions")
        self.assertContains(r, "Personal Info")

    def test_admin_add_superuser_org_not_required(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        params = dict(
            username="testadd",
            email="test@testadd.com",
            password1="tester",
            password2="tester",
            is_staff=True,
            is_superuser=True,
        )
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        params.update(
            {
                f"{self.app_label}_organizationuser-TOTAL_FORMS": 1,
                f"{self.app_label}_organizationuser-INITIAL_FORMS": 0,
                f"{self.app_label}_organizationuser-MIN_NUM_FORMS": 0,
                f"{self.app_label}_organizationuser-MAX_NUM_FORMS": 1,
            }
        )
        res = self.client.post(
            reverse(f"admin:{self.app_label}_user_add"), params, follow=True
        )
        self.assertNotContains(res, "errors field-organization")
        self.assertNotContains(res, "Please correct the errors below.")
        queryset = User.objects.filter(username="testadd")
        self.assertEqual(queryset.count(), 1)
        user = queryset.first()
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_operator_change_user_permissions(self):
        operator = self._create_operator_with_user_permissions()
        self.client.force_login(operator)
        admin = self._create_admin()
        response = self.client.get(
            reverse(f"admin:{self.app_label}_user_change", args=[admin.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_user_add_user(self):
        admin = self._create_administrator()
        self.client.force_login(admin)
        # removing the "add_organizationuser" permission allows
        # achieving more test coverage
        add_organizationuser = Permission.objects.get(
            codename__endswith="add_organizationuser"
        )
        admin.user_permissions.remove(add_organizationuser)
        response = self.client.get(reverse(f"admin:{self.app_label}_user_add"))
        self.assertContains(response, '<input type="text" name="username"')

    def test_organization_owner(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        self._create_org_owner()
        response = self.client.get(
            reverse(f"admin:{self.app_label}_organizationowner_changelist")
        )
        self.assertContains(response, "tester")

    def test_first_org_manager_creates_org_owner(self):
        org = self._get_org()
        user = self._get_user()
        org_user = self._create_org_user(organization=org, user=user, is_admin=True)
        org_owner_qs = OrganizationOwner.objects.all()
        self.assertEqual(org_owner_qs.count(), 1)
        org_owner = org_owner_qs.first()
        self.assertEqual(org_owner.organization, org)
        self.assertEqual(org_owner.organization_user, org_user)

    def test_first_org_member_creates_no_org_owner(self):
        org = self._get_org()
        user = self._get_user()
        self._create_org_user(organization=org, user=user, is_admin=False)
        org_owner_qs = OrganizationOwner.objects.all()
        self.assertEqual(org_owner_qs.count(), 0)

    def test_second_orguser_creates_no_org_owner(self):
        org = self._get_org()
        user = self._get_user()
        org_user = self._create_org_user(organization=org, user=user, is_admin=True)
        user1 = self._create_user(username="user1", email="user1@gmail.com")
        self._create_org_user(organization=org, user=user1, is_admin=True)
        org_owner_qs = OrganizationOwner.objects.all()
        self.assertEqual(org_owner_qs.count(), 1)
        org_owner = org_owner_qs.first()
        self.assertEqual(org_owner.organization, org)
        self.assertEqual(org_owner.organization_user, org_user)

    def test_organzation_add_inline_owner_absent(self):
        self.client.force_login(self._get_admin())
        response = self.client.get(reverse(f"admin:{self.app_label}_organization_add"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Organization owners")

    def test_organzation_change_inline_owner_present(self):
        org = self._create_org()
        self.client.force_login(self._get_admin())
        response = self.client.get(
            reverse(f"admin:{self.app_label}_organization_change", args=[org.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Organization owner")

    @patch.object(
        OrganizationOwner, "full_clean", side_effect=ValidationError("invalid")
    )
    @patch.object(apps_logger, "exception")
    def test_invalid_org_owner(self, mocked_owner, logger_exception):
        org = self._create_org(name="invalid")
        user = self._create_user(username="invalid", email="invalid@email.com")
        org_user = self._create_org_user(organization=org, user=user, is_admin=True)
        mocked_owner.assert_called_once()
        logger_exception.assert_called_once()
        owner_qs = OrganizationOwner.objects.filter(organization_user=org_user)
        self.assertEqual(owner_qs.count(), 0)

    def test_organization_uuid_field(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse(f"admin:{self.app_label}_organization_add"))
        html = '<input type="text" name="name" value="default"'
        self.assertNotContains(response, html)

    def test_action_active(self):
        user = User.objects.create(
            username="openwisp",
            password="test",
            email="openwisp@test.com",
            is_active=False,
        )
        path = reverse(f"admin:{self.app_label}_user_changelist")
        self.client.force_login(self._get_admin())
        post_data = {
            "_selected_action": [user.pk],
            "action": "make_active",
            "csrfmiddlewaretoken": "test",
            "confirmation": "Confirm",
        }
        response = self.client.post(path, post_data, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_action_active_perms(self):
        org = self._get_org()
        org_user = self._create_org_user(
            organization=org, is_admin=True, user=self._create_user(is_staff=True)
        ).user
        user_obj = self._create_org_user(
            organization=org,
            user=self._create_user(
                username="active-user", email="active-user@example.com"
            ),
        ).user
        self._test_action_permission(
            path=reverse(f"admin:{self.app_label}_user_changelist"),
            action="make_active",
            user=org_user,
            obj=user_obj,
            message="Successfully made 1 user active.",
            required_perms=["change"],
            extra_payload={"confirmation": True},
        )

    def test_action_inactive(self):
        user = User.objects.create(
            username="openwisp",
            password="test",
            email="openwisp@test.com",
            is_active=True,
        )
        path = reverse(f"admin:{self.app_label}_user_changelist")
        self.client.force_login(self._get_admin())
        post_data = {
            "_selected_action": [user.pk],
            "action": "make_inactive",
            "csrfmiddlewaretoken": "test",
            "confirmation": "Confirm",
        }
        response = self.client.post(path, post_data, follow=True)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(response.status_code, 200)

    def test_action_inactive_perms(self):
        org = self._get_org()
        org_user = self._create_org_user(
            organization=org, is_admin=True, user=self._create_user(is_staff=True)
        ).user
        user_obj = self._create_org_user(
            organization=org,
            user=self._create_user(
                username="active-user", email="active-user@example.com"
            ),
        ).user
        self._test_action_permission(
            path=reverse(f"admin:{self.app_label}_user_changelist"),
            action="make_inactive",
            user=org_user,
            obj=user_obj,
            message="Successfully made 1 user inactive.",
            required_perms=["change"],
            extra_payload={"confirmation": True},
        )

    def test_action_confirmation_page(self):
        user = User.objects.create(
            username="openwisp",
            password="test",
            email="openwisp@test.com",
            is_active=True,
        )
        path = reverse(f"admin:{self.app_label}_user_changelist")
        self.client.force_login(self._get_admin())
        post_data = {
            "_selected_action": [user.pk],
            "action": "make_active",
            "csrfmiddlewaretoken": "test",
        }
        response = self.client.post(path, post_data, follow=True)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(response.status_code, 200)

    def test_superuser_delete_operator(self):
        user = self._create_operator()
        org = self._create_org()
        org_user = self._create_org_user(user=user, organization=org, is_admin=True)
        post_data = {
            "_selected_action": [user.pk],
            "action": "delete_selected",
            "post": "yes",
        }
        self.client.force_login(self._get_admin())
        path = reverse(f"admin:{self.app_label}_user_changelist")
        r = self.client.post(path, post_data, follow=True)
        user_qs = User.objects.filter(pk=user.pk)
        org_user_qs = OrganizationUser.objects.filter(pk=org_user.pk)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(user_qs.count(), 0)
        self.assertEqual(org_user_qs.count(), 0)

    def test_delete_selected_overridden_action_perms(self):
        org = self._get_org()
        administrator_group = Group.objects.get(name="Administrator")
        administrator_group.permissions.remove(
            Permission.objects.get(codename=f"delete_{User._meta.model_name}")
        )
        administrator = self._create_administrator([org])

        user_obj = self._create_org_user(
            organization=org,
            user=self._create_user(
                username="delete-user", email="delete-user@example.com"
            ),
        ).user
        self._test_action_permission(
            path=reverse(f"admin:{self.app_label}_user_changelist"),
            action="delete_selected_overridden",
            user=administrator,
            obj=user_obj,
            message="Successfully deleted 1 user.",
            required_perms=["delete"],
            extra_payload={"post": "yes"},
        )

    def test_staff_delete_staff(self):
        org = self._create_org()
        staff = self._create_user(
            username="staff", is_staff=True, email="staff@gmail.com"
        )
        group = Group.objects.filter(name="Administrator")
        staff.groups.set(group)
        self._create_org_user(organization=org, user=staff, is_admin=True)
        op = self._create_operator()
        op.groups.set(group)
        self._create_org_user(organization=org, user=op, is_admin=True)
        post_data = {
            "_selected_action": [op.pk],
            "action": "delete_selected_overridden",
            "post": "yes",
        }
        path = reverse(f"admin:{self.app_label}_user_changelist")
        self.client.force_login(staff)
        r = self.client.post(path, post_data, follow=True)
        user_qs = User.objects.filter(pk=op.pk)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(user_qs.count(), 0)
        self.assertContains(r, "Successfully deleted 1 user")

    def test_superuser_delete_staff(self):
        org = self._create_org()
        group = Group.objects.filter(name="Administrator")
        op = self._create_operator()
        op.groups.set(group)
        self._create_org_user(organization=org, user=op, is_admin=True)
        post_data = {
            "_selected_action": [op.pk],
            "action": "delete_selected_overridden",
            "post": "yes",
        }
        path = reverse(f"admin:{self.app_label}_user_changelist")
        self.client.force_login(self._get_admin())
        r = self.client.post(path, post_data, follow=True)
        user_qs = User.objects.filter(pk=op.pk)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(user_qs.count(), 0)
        self.assertContains(r, "Successfully deleted 1 user")

    def test_staff_delete_org_owner(self):
        org = self._create_org()
        staff = self._create_user(
            username="staff", is_staff=True, email="staff@gmail.com"
        )
        group = Group.objects.filter(name="Administrator")
        staff.groups.set(group)
        op = self._create_operator()
        op.groups.set(group)
        self._create_org_user(organization=org, user=op, is_admin=True)
        self._create_org_user(organization=org, user=staff, is_admin=True)
        path = reverse(f"admin:{self.app_label}_user_changelist")
        post_data = {
            "action": "delete_selected_overridden",
            "_selected_action": [op.pk],
            "post": "yes",
        }
        self.client.force_login(staff)
        r = self.client.post(path, post_data, follow=True)
        user_qs = User.objects.filter(pk=op.pk)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f"delete 1 organization owner: {op.username}")
        self.assertEqual(user_qs.count(), 1)

    def test_superuser_delete_org_owner(self):
        org = self._create_org()
        group = Group.objects.filter(name="Administrator")
        op = self._create_operator()
        op.groups.set(group)
        self._create_org_user(organization=org, user=op, is_admin=True)
        path = reverse(f"admin:{self.app_label}_user_changelist")
        post_data = {
            "action": "delete_selected_overridden",
            "_selected_action": [op.pk],
            "post": "yes",
        }
        self.client.force_login(self._get_admin())
        r = self.client.post(path, post_data, follow=True)
        user_qs = User.objects.filter(pk=op.pk)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Successfully deleted 1 user")
        self.assertEqual(user_qs.count(), 0)

    def test_staff_bulk_delete(self):
        org = self._create_org()
        group = Group.objects.filter(name="Administrator")
        staff = self._create_user(
            username="staff", is_staff=True, email="staff@gmail.com"
        )
        staff.groups.set(group)
        op1 = self._create_user(username="op1", is_staff=True, email="op1@gmail.com")
        op2 = self._create_user(username="op2", is_staff=True, email="op2@gmail.com")
        op1.groups.set(group)
        op2.groups.set(group)
        self._create_org_user(organization=org, user=op1, is_admin=True)
        self._create_org_user(organization=org, user=op2, is_admin=True)
        self._create_org_user(organization=org, user=staff, is_admin=True)
        post_data = {
            "action": "delete_selected_overridden",
            "_selected_action": [op1.pk, op2.pk],
        }
        path = reverse(f"admin:{self.app_label}_user_changelist")
        self.client.force_login(staff)
        r = self.client.post(path, post_data, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f"delete 1 organization owner: {op1.username}")
        post_data.update({"post": "yes"})
        r = self.client.post(path, post_data, follow=True)
        user_qs = User.objects.all()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Successfully deleted 1 user")
        self.assertEqual(user_qs.count(), 3)
        self.assertEqual(user_qs.filter(pk=op2.pk).count(), 0)
        self.assertEqual(user_qs.filter(pk=op1.pk).count(), 1)

    def test_superuser_bulk_delete(self):
        org = self._create_org()
        group = Group.objects.filter(name="Administrator")
        op1 = self._create_user(username="op1", is_staff=True, email="op1@gmail.com")
        op2 = self._create_user(username="op2", is_staff=True, email="op2@gmail.com")
        op1.groups.set(group)
        op2.groups.set(group)
        self._create_org_user(organization=org, user=op1, is_admin=True)
        self._create_org_user(organization=org, user=op2, is_admin=True)
        post_data = {
            "action": "delete_selected_overridden",
            "_selected_action": [op1.pk, op2.pk],
            "post": "yes",
        }
        path = reverse(f"admin:{self.app_label}_user_changelist")
        self.client.force_login(self._get_admin())
        r = self.client.post(path, post_data, follow=True)
        user_qs = User.objects.all()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Successfully deleted 2 users")
        self.assertEqual(user_qs.count(), 2)

    def test_admin_user_has_change_org_perm(self):
        user = self._get_user()
        group = Group.objects.filter(name="Administrator")
        user.groups.set(group)
        self.assertIn(
            f"{self.app_label}.change_organization", user.get_all_permissions()
        )

    def test_can_change_org(self):
        org = self._get_org()
        user = self._create_user(
            username="change", password="change", email="email@email.com", is_staff=True
        )
        group = Group.objects.filter(name="Administrator")
        user.groups.set(group)
        org_user = self._create_org_user(user=user, organization=org, is_admin=True)
        path = reverse(f"admin:{self.app_label}_organization_change", args=[org.pk])

        with self.subTest("org owner can change org"):
            self.client.force_login(user)
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, f'<input type="text" name="name" value="{org.name}"')

        with self.subTest("managers can change org"):
            OrganizationOwner.objects.all().delete()
            self.client.force_login(user)
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, f'<input type="text" name="name" value="{org.name}"')

        with self.subTest("member can not edit org"):
            OrganizationOwner.objects.all().delete()
            org_user.is_admin = False
            org_user.save()
            self.client.force_login(user)
            r = self.client.get(path)
            self.assertEqual(r.status_code, 302)

    def test_only_superuser_has_add_delete_org_perm(self):
        user = self._create_user(
            username="change", password="change", email="email@email.com", is_staff=True
        )
        group = Group.objects.filter(name="Administrator")
        user.groups.set(group)
        org = self._get_org()
        add_params = {
            "name": "new org",
            "slug": "new",
            "owner-TOTAL_FORMS": "0",
            "owner-INITIAL_FORMS": "0",
            "owner-MIN_NUM_FORMS": "0",
            "owner-MAX_NUM_FORMS": "1",
        }
        delete_params = {
            "action": "delete_selected",
            "_selected_action": [org.pk],
            "post": "yes",
        }
        add_params.update(self._get_org_edit_form_inline_params(user, org))
        add_path = reverse(f"admin:{self.app_label}_organization_add")
        delete_path = reverse(f"admin:{self.app_label}_organization_changelist")

        with self.subTest("Administrators can not add org"):
            self.client.force_login(user)
            r = self.client.post(add_path, add_params, follow=True)
            self.assertEqual(r.status_code, 403)
            orgs = Organization.objects.filter(slug="new")
            self.assertEqual(orgs.count(), 0)

        with self.subTest("Administrators can not delete org"):
            self.client.force_login(user)
            r = self.client.post(delete_path, delete_params, follow=True)
            self.assertEqual(r.status_code, 200)
            orgs = Organization.objects.filter(pk=org.pk)
            self.assertEqual(orgs.count(), 1)

        with self.subTest("superuser can add org"):
            self.client.force_login(self._get_admin())
            r = self.client.post(add_path, add_params, follow=True)
            self.assertEqual(r.status_code, 200)
            orgs = Organization.objects.get(name="new org")
            self.assertEqual(orgs.name, "new org")

        with self.subTest("superuser can delete org"):
            self.client.force_login(self._get_admin())
            r = self.client.post(delete_path, delete_params, follow=True)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "Successfully deleted 1 organization")
            orgs = Organization.objects.filter(pk=org.pk)
            self.assertEqual(orgs.count(), 0)

    def test_can_change_inline_org_owner(self):
        user1 = self._create_user(
            username="user1", password="user1", email="email1@email.com", is_staff=True
        )
        user2 = self._create_user(
            username="user2", password="user2", email="email2@email.com", is_staff=True
        )
        group = Group.objects.filter(name="Administrator")
        user1.groups.set(group)
        user2.groups.set(group)
        org = self._get_org()
        org_user = self._create_org_user(user=user1, organization=org, is_admin=True)
        org_owner = OrganizationOwner.objects.get(organization_user=org_user)
        org_user2 = self._create_org_user(organization=org, user=user2, is_admin=True)
        params = {
            "name": org.name,
            "slug": org.slug,
            "is_active": "on",
            "owner-TOTAL_FORMS": "1",
            "owner-INITIAL_FORMS": "1",
            "owner-MIN_NUM_FORMS": "0",
            "owner-MAX_NUM_FORMS": "1",
            "owner-0-organization_user": f"{org_user.pk}",
            "owner-0-organization": f"{org.pk}",
            "owner-0-id": f"{org_owner.pk}",
        }
        path = reverse(f"admin:{self.app_label}_organization_change", args=[org.pk])
        with self.subTest("manager can not edit inline org owner"):
            self.client.force_login(user2)
            params.update(self._get_org_edit_form_inline_params(user2, org))
            params.update({"owner-0-organization_user": f"{org_user2.pk}"})
            r = self.client.post(path, params, follow=True)
            self.assertEqual(r.status_code, 200)
            org_owners = OrganizationOwner.objects.filter(organization_user=org_user2)
            self.assertEqual(org_owners.count(), 0)

        with self.subTest("owner can edit inline org owner"):
            self.client.force_login(user1)
            params.update(self._get_org_edit_form_inline_params(user1, org))
            params.update({"owner-0-organization_user": f"{org_user2.pk}"})
            r = self.client.post(path, params, follow=True)
            self.assertEqual(r.status_code, 200)
            org_owners = OrganizationOwner.objects.filter(organization_user=org_user2)
            self.assertEqual(org_owners.count(), 1)

        with self.subTest("superuser can edit inline org owner"):
            params.update(self._get_org_edit_form_inline_params(self._get_admin(), org))
            self.client.force_login(self._get_admin())
            user3 = self._create_user(
                username="user3",
                password="user3",
                email="email3@email.com",
                is_staff=True,
            )
            user3.groups.set(group)
            org_user3 = self._create_org_user(
                organization=org, user=user3, is_admin=True
            )
            params.update({"owner-0-organization_user": f"{org_user3.pk}"})
            r = self.client.post(path, params, follow=True)
            self.assertEqual(r.status_code, 200)
            org_owners = OrganizationOwner.objects.filter(organization_user=org_user3)
            self.assertEqual(org_owners.count(), 1)

    def test_only_superuser_can_delete_inline_org_owner(self):
        org = self._get_org()
        user = self._create_user(
            username="change", password="change", email="email@email.com", is_staff=True
        )
        group = Group.objects.filter(name="Administrator")
        user.groups.set(group)
        self._create_org_user(organization=org, user=user, is_admin=True)
        path = reverse(f"admin:{self.app_label}_organization_change", args=[org.pk])

        with self.subTest("org owners can not delete inline org owner"):
            self.client.force_login(user)
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, '-DELETE">Delete')

        with self.subTest("managers can not delete inline org owner"):
            user1 = self._create_user(
                username="change1",
                password="change1",
                email="email1@email.com",
                is_staff=True,
            )
            user1.groups.set(group)
            self._create_org_user(organization=org, user=user1, is_admin=True)
            self.client.force_login(user1)
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, '-DELETE">Delete')

        with self.subTest("superuser can delete inline org owner"):
            self.client.force_login(self._get_admin())
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, '-DELETE">Delete')

    def test_delete_org_user(self):
        self.client.force_login(self._get_admin())
        user1 = self._create_user(username="user1", email="user1@email.com")
        org1 = self._create_org(name="org1")
        org_user = self._create_org_user(user=user1, organization=org1, is_admin=True)

        with self.subTest("test delete org user which belongs to owner"):
            post_data = {"post": "yes"}
            url = reverse(
                f"admin:{self.app_label}_organizationuser_delete", args=[org_user.pk]
            )
            r = self.client.post(url, post_data, follow=True)
            qs = OrganizationUser.objects.filter(organization=org1, user=user1)
            self.assertEqual(r.status_code, 200)
            msg = (
                "t delete this organization user because it "
                "belongs to an organization owner"
            )
            self.assertContains(r, msg)
            self.assertEqual(qs.count(), 1)

        with self.subTest("test delete org user which belongs to no owner"):
            org2 = self._create_org(name="org2")
            org_u = self._create_org_user(user=user1, organization=org2, is_admin=False)
            post_data = {"post": "yes"}
            url = reverse(
                f"admin:{self.app_label}_organizationuser_delete", args=[org_u.pk]
            )
            r = self.client.post(url, post_data, follow=True)
            qs = OrganizationUser.objects.filter(organization=org2, user=user1)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "was deleted successfully.")
            self.assertEqual(qs.count(), 0)

        with self.subTest("Can not delete only owner's org user with action"):
            post_data = {
                "action": "delete_selected_overridden",
                "_selected_action": [org_user.pk],
                "post": "yes",
            }
            url = reverse(f"admin:{self.app_label}_organizationuser_changelist")
            # django-reversion adds ~4 queries
            with self.assertNumQueries(12):
                r = self.client.post(url, post_data, follow=True)
            qs = OrganizationUser.objects.filter(user=user1, organization=org1)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "t delete organization users which belong to owners")
            self.assertEqual(qs.count(), 1)

        with self.subTest("delete org users with some belonging to owners"):
            org2 = self._create_org(name="org2")
            org_user2 = self._create_org_user(user=user1, organization=org2)
            post_data = {
                "action": "delete_selected_overridden",
                "_selected_action": [org_user.pk, org_user2.pk],
            }
            url = reverse(f"admin:{self.app_label}_organizationuser_changelist")
            r = self.client.post(url, post_data, follow=True)
            self.assertEqual(r.status_code, 200)
            msg = (
                "t delete 1 organization user because "
                "it belongs to an organization owner"
            )
            self.assertContains(r, msg)
            post_data.update({"post": "yes"})
            # django-reversion adds ~4 queries
            with self.assertNumQueries(21):
                r = self.client.post(url, post_data, follow=True)
            qs = OrganizationUser.objects.filter(pk__in=[org_user.pk, org_user2.pk])
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "Successfully deleted 1 organization user.")
            self.assertEqual(qs.count(), 1)
            self.assertEqual(qs.first().organization, org1)

    def test_delete_selected_overridden_org_user_action_perms(self):
        org = self._get_org()
        user = self._create_org_user(
            organization=org, is_admin=True, user=self._create_user(is_staff=True)
        ).user
        org_user_obj = self._create_org_user(
            organization=org,
            user=self._create_user(
                username="delete-user", email="delete-user@example.com"
            ),
        )
        self._test_action_permission(
            path=reverse(f"admin:{self.app_label}_organizationuser_changelist"),
            action="delete_selected_overridden",
            user=user,
            obj=org_user_obj,
            message="Successfully deleted 1 organization user.",
            required_perms=["delete"],
            extra_payload={"post": "yes"},
        )

    @capture_any_output()
    def test_admin_add_user_with_invalid_email(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        params = dict(
            username="testmail",
            email="test@invalid.com",
            password1="tester",
            password2="tester",
        )
        params.update(self.add_user_inline_params)
        params.update(self._additional_params_add())
        with patch("allauth.account.models.EmailAddress.objects.add_email") as mocked:
            mocked.side_effect = smtplib.SMTPSenderRefused(
                501, "5.1.7 Bad sender address syntax", "test_name@test_domain"
            )
            self.client.post(reverse(f"admin:{self.app_label}_user_add"), params)
            mocked.assert_called_once()

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for User, Organization,
        # Organization Owner and Organization User models
        admin = self._create_admin()
        self.client.force_login(admin)
        models = [
            "user",
            "organization",
            "organizationowner",
            "organizationuser",
            "group",
        ]
        response = self.client.get(reverse("admin:index"))
        for model in models:
            with self.subTest(f"test menu group link for {model} model"):
                url = reverse(f"admin:{self.app_label}_{model}_changelist")
                self.assertContains(response, f'class="mg-link" href="{url}"')
        with self.subTest("test user and organization group is registered"):
            self.assertContains(
                response,
                '<div class="mg-dropdown-label">Users & Organizations </div>',
                html=True,
            )


class TestBasicUsersIntegration(
    TestOrganizationMixin, TestUserAdditionalFieldsMixin, TestCase
):
    """
    tests basic integration with openwisp_users
    (designed to be inherited in other openwisp modules)
    """

    app_label = "openwisp_users"
    is_integration_test = True

    def _get_user_edit_form_inline_params(self, user, organization):
        params = {
            # email address inline
            "emailaddress_set-TOTAL_FORMS": 1,
            "emailaddress_set-INITIAL_FORMS": 1,
            "emailaddress_set-MIN_NUM_FORMS": 0,
            "emailaddress_set-MAX_NUM_FORMS": 0,
            "emailaddress_set-0-verified": True,
            "emailaddress_set-0-primary": True,
            "emailaddress_set-0-id": user.emailaddress_set.first().id,
            "emailaddress_set-0-user": str(user.pk),
        }

        try:
            organization_user = OrganizationUser.objects.get(
                user=user, organization=organization
            )
        except OrganizationUser.DoesNotExist:
            pass
        else:
            params.update(
                {
                    # organization user inline
                    f"{self.app_label}_organizationuser-TOTAL_FORMS": 1,
                    f"{self.app_label}_organizationuser-INITIAL_FORMS": 1,
                    f"{self.app_label}_organizationuser-MIN_NUM_FORMS": 0,
                    f"{self.app_label}_organizationuser-MAX_NUM_FORMS": 1000,
                    f"{self.app_label}_organizationuser-0-is_admin": False,
                    f"{self.app_label}_organizationuser-0-organization": str(
                        organization.pk
                    ),
                    f"{self.app_label}_organizationuser-0-id": str(
                        organization_user.pk
                    ),
                    f"{self.app_label}_organizationuser-0-user": str(user.pk),
                }
            )
        return params

    def test_change_user(self):
        admin = self._create_admin()
        user = self._create_user()
        org = Organization.objects.first()
        self._create_org_user(organization=org, user=user)
        self.client.force_login(admin)
        params = user.__dict__
        params["bio"] = "Test change"
        params.pop("phone_number")
        params.pop("password", None)
        params.pop("_password", None)
        params.pop("last_login")
        params.pop("password_updated")
        params["birth_date"] = user.date_joined.date()
        params = self._additional_params_pop(params)
        params.update(self._get_user_edit_form_inline_params(user, org))
        url = reverse(f"admin:{self.app_label}_user_change", args=[user.pk])
        response = self.client.post(
            url,
            params,
            follow=True,
        )
        self.assertNotContains(response, "Please correct the error below.")
        user.refresh_from_db()
        self.assertEqual(user.bio, params["bio"])
        self.assertEqual(user.birth_date, params["birth_date"])
        with self.subTest("test presence of fields"):
            response = self.client.get(url)
            self.assertContains(response, "id_birth_date")
            self.assertContains(response, "notes for internal usage")

    def _delete_inline_org_user(self, is_admin=False):
        admin = self._create_admin()
        user = self._create_user()
        org = self._create_org(name="inline-org")
        self._create_org_user(organization=org, user=user, is_admin=is_admin)
        self.client.force_login(admin)
        params = user.__dict__
        params.pop("phone_number")
        params.pop("password", None)
        params.pop("_password", None)
        params.pop("last_login")
        params.pop("password_updated")
        params = self._additional_params_pop(params)
        params.update(self._get_user_edit_form_inline_params(user, org))
        params.update({f"{self.app_label}_organizationuser-0-DELETE": "on"})
        path = reverse(f"admin:{self.app_label}_user_change", args=[user.pk])

        r = self.client.post(path, params, follow=True)
        qs = OrganizationUser.objects.filter(user=user)
        self.assertEqual(r.status_code, 200)
        if is_admin:
            single_msg = (
                "t delete 1 organization user because it "
                "belongs to an organization owner."
            )
            self.assertContains(r, single_msg)
            self.assertEqual(qs.count(), 1)
        else:
            self.assertEqual(qs.count(), 0)

    def test_delete_inline_org_user(self):
        self._delete_inline_org_user()

    def test_delete_inline_owner_org_user(self):
        self._delete_inline_org_user(is_admin=True)

    def test_login_page(self):
        r = self.client.get(reverse("admin:login"))

        with self.subTest("Test forgot password link"):
            self.assertContains(
                r, '<a href="/accounts/password/reset/">Forgot Password?</a'
            )

        with self.subTest("Test username label"):
            self.assertContains(r, '<label class="required" for="id_username">')
            self.assertContains(r, "Email, phone number or username:")


class TestMultitenantAdmin(TestMultitenantAdminMixin, TestCase):
    app_label = "openwisp_users"

    def _create_multitenancy_test_env(self):
        org1 = self._create_org(name="organization1")
        org2 = self._create_org(name="organization2")
        org3 = self._create_org(name="organization3")
        user1 = self._create_user(username="user1", email="user1j@something.com")
        user12 = self._create_user(username="user12", email="user12j@something.com")
        user2 = self._create_user(username="user2", email="user2j@something.com")
        user22 = self._create_user(username="user22", email="user22j@something.com")
        user23 = self._create_user(
            username="user23", email="user23j@something.com", is_superuser=True
        )
        user3 = self._create_user(username="user3", email="user3@something.com")
        organization_user1 = self._create_org_user(
            organization=org1, user=user1, is_admin=True
        )
        organization_user12 = self._create_org_user(organization=org1, user=user12)
        organization_user2 = self._create_org_user(organization=org2, user=user2)
        organization_user22 = self._create_org_user(organization=org2, user=user22)
        organization_owner1 = OrganizationOwner.objects.get(
            organization_user=organization_user1, organization=org1
        )
        organization_owner2 = self._create_org_owner(
            organization_user=organization_user2, organization=org2
        )
        operator = self._create_operator()
        organization_user3 = self._create_org_user(
            organization=org3, user=operator, is_admin=True
        )
        administrator = self._create_administrator()
        organization_user4 = self._create_org_user(
            organization=org3, user=administrator, is_admin=True
        )
        organization_user31 = self._create_org_user(organization=org3, user=user3)
        organization_user1o = self._create_org_user(organization=org1, user=operator)
        organization_user1a = self._create_org_user(
            organization=org1, user=administrator
        )
        data = dict(
            org1=org1,
            org2=org2,
            org3=org3,
            user1=user1,
            user2=user2,
            user12=user12,
            user22=user22,
            user23=user23,
            user3=user3,
            organization_user1=organization_user1,
            organization_user2=organization_user2,
            organization_user12=organization_user12,
            organization_user22=organization_user22,
            organization_user3=organization_user3,
            organization_user4=organization_user4,
            organization_user1o=organization_user1o,
            organization_user1a=organization_user1a,
            organization_user31=organization_user31,
            organization_owner1=organization_owner1,
            organization_owner2=organization_owner2,
            operator=operator,
            administrator=administrator,
        )
        return data

    def _make_org_manager(self, user, org):
        ou = OrganizationUser.objects.get(organization=org, user=user)
        ou.is_admin = True
        ou.save()

    def test_multitenancy_organization_user_queryset(self):
        data = self._create_multitenancy_test_env()
        self._make_org_manager(data["administrator"], data["org1"])
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_organizationuser_changelist"),
            hidden=[
                data["organization_user2"].user.username,
                data["organization_user22"].user.username,
            ],
            visible=[
                data["organization_user1"].user.username,
                data["organization_user12"].user.username,
                data["organization_user1o"].user.username,
                data["organization_user3"].user.username,
            ],
            administrator=True,
        )

    def test_multitenancy_organization_owner_queryset(self):
        data = self._create_multitenancy_test_env()
        self._make_org_manager(data["administrator"], data["org1"])
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_organizationowner_changelist"),
            hidden=[data["organization_owner2"].organization_user.user.username],
            visible=[data["organization_owner1"].organization_user.user.username],
            administrator=True,
        )

    def test_useradmin_specific_multitenancy_costraints(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_user_changelist"),
            visible=[data["user3"], data["operator"]],
            hidden=[data["user2"], data["user22"], data["user1"], data["user12"]],
            administrator=True,
        )

    def test_multitenant_admin_manager_only(self):
        staff = self._create_user(
            username="staff__user", email="staff@staff.org", is_staff=True
        )
        staff_org = self._create_org(name="staff_org")
        other_org = Organization.objects.create(name="other org", slug="other-org")
        admin_group = Group.objects.get(name="Administrator")
        staff.groups.add(admin_group)
        self._create_org_user(organization=other_org, user=staff, is_admin=False)
        self._create_org_user(organization=staff_org, user=staff, is_admin=True)
        self._login(staff.username)
        user1 = self._create_user(username="user1__otherorg", email="user1@user1.org")
        self._create_org_user(organization=other_org, user=user1, is_admin=False)
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_organizationuser_changelist"),
            hidden=[user1.username],
            visible=[staff.username],
        )

    def test_staff_user_manager_of_multiple_orgs_bug(self):
        staff = self._create_user(
            username="staff__user", email="staff@staff.org", is_staff=True
        )
        staff_org = self._create_org(name="staff_org")
        other_org = Organization.objects.create(name="other org", slug="other-org")
        admin_group = Group.objects.get(name="Administrator")
        staff.groups.add(admin_group)
        self._create_org_user(organization=other_org, user=staff, is_admin=True)
        self._create_org_user(organization=staff_org, user=staff, is_admin=True)
        self._login(staff.username)
        response = self.client.get(reverse(f"admin:{self.app_label}_user_changelist"))
        self.assertContains(response, staff.email, count=1)

    def test_class_attr_regression(self):
        class TestAdmin(MultitenantAdminMixin):
            multitenant_parent = "test"

        owner_admin = OrganizationOwnerAdmin(Organization, django_admin.site)

        test_admin = TestAdmin()
        with self.subTest("multitenant_parent added to multitenant_shared_relations"):
            self.assertIn("test", test_admin.multitenant_shared_relations)
        with self.subTest("mutable data structure of sibling class unaffected"):
            self.assertNotIn("test", owner_admin.multitenant_shared_relations)
        with self.subTest("original attribute unaffected"):
            self.assertIsNone(MultitenantAdminMixin.multitenant_shared_relations)

    def test_organization_user_filter(self):
        data = self._create_multitenancy_test_env()
        self._make_org_manager(data["administrator"], data["org1"])
        url = reverse("admin:ow-auto-filter")
        payload = {
            "app_label": self.app_label,
            "model_name": "user",
            "field_name": f"{self.app_label}_organization",
        }

        with self.subTest("test superadmin"):
            user = User.objects.filter(is_superuser=True, is_staff=True).first()
            self.client.force_login(user)
            response = self.client.get(url, payload)
            self.assertEqual(response.status_code, 200)
            for option in response.json()["results"]:
                assert option["id"] in [
                    str(id) for id in Organization.objects.values_list("id", flat=True)
                ]

        with self.subTest("test non superadmin"):
            user = User.objects.get(username="administrator")
            self.client.force_login(user)
            response = self.client.get(url, payload)
            self.assertEqual(response.status_code, 200)
            for option in response.json()["results"]:
                assert option["id"] in [str(id) for id in user.organizations_managed]
                assert option["id"] not in Organization.objects.exclude(
                    pk__in=user.organizations_managed
                )


class TestUserPasswordExpiration(TestOrganizationMixin, TestCase):
    @patch.object(app_settings, "STAFF_USER_PASSWORD_EXPIRATION", 30)
    def test_expired_password_user_redirected(self):
        self.client.logout()
        user = self._create_admin()
        user.password_updated = now().date() - timedelta(days=31)
        user.save()
        login_response = self.client.post(
            reverse("admin:login"),
            data={"username": user.username, "password": "tester"},
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.url, "/accounts/password/change/?next=/admin/")

        change_password_response = self.client.get(login_response.url)
        self.assertEqual(change_password_response.status_code, 200)
        self.assertContains(
            change_password_response,
            "Your password has expired, please update your password.",
        )

    @patch.object(app_settings, "STAFF_USER_PASSWORD_EXPIRATION", 30)
    def test_non_expired_user_django_redirection(self):
        self.client.logout()
        redirect_url = reverse("admin:sites_site_changelist")
        user = self._create_admin()
        user.set_password("tester")
        user.save()
        login_response = self.client.post(
            "{0}?next={1}".format(reverse("admin:login"), redirect_url),
            data={"username": user.username, "password": "tester"},
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(
            login_response.url,
            redirect_url,
        )

    @patch.object(app_settings, "STAFF_USER_PASSWORD_EXPIRATION", 30)
    def test_redirection_for_expired_user_after_password_update(self):
        """
        This test ensures that user is confined to change password
        page until they change thier password.
        """
        self.client.logout()
        user = self._create_admin()
        user.password_updated = now().date() - timedelta(days=31)
        user.save()
        self.client.force_login(user)
        site_changelist_path = reverse("admin:sites_site_changelist")
        password_change_redirect_response = self.client.get(site_changelist_path)
        self.assertEqual(password_change_redirect_response.status_code, 302)
        self.assertEqual(
            password_change_redirect_response.url,
            "{0}?{1}={2}".format(
                reverse("account_change_password"),
                REDIRECT_FIELD_NAME,
                site_changelist_path,
            ),
        )
        response = self.client.get(password_change_redirect_response.url)
        self.assertContains(
            response, "Your password has expired, please update your password."
        )
        change_password_response = self.client.post(
            password_change_redirect_response.url,
            data={
                "oldpassword": "tester",
                "password1": "newpassword",
                "password2": "newpassword",
                "next": site_changelist_path,
            },
            follow=True,
        )
        self.assertContains(
            change_password_response,
            (
                '<ul class="messagelist">\n'
                '<li class="success">Password successfully changed.</li>\n'
                "</ul>"
            ),
            html=True,
        )
        self.assertEqual(
            change_password_response.request.get("PATH_INFO"), site_changelist_path
        )

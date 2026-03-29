import django
from allauth.account.models import EmailAddress
from django.contrib import auth
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_utils.tests import AssertNumQueriesSubTestMixin

from ..utils import TestOrganizationMixin

Organization = load_model("openwisp_users", "Organization")
User = get_user_model()
Group = load_model("openwisp_users", "Group")
OrganizationUser = load_model("openwisp_users", "OrganizationUser")


class TestUsersApi(
    AssertNumQueriesSubTestMixin,
    TestOrganizationMixin,
    TestCase,
):
    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username="administrator", password="admin", email="test@test.org"
        )
        self.client.force_login(user)

    # Tests for Organization Model API endpoints
    def test_organization_list_api(self):
        path = reverse("users:organization_list")
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)

    def test_organization_list_nonsuperuser_api(self):
        user = self._create_user()
        view_perm = Permission.objects.filter(codename="view_organization")
        user.user_permissions.add(*view_perm)
        self.client.force_login(user)
        path = reverse("users:organization_list")
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 0)
        self.assertEqual(Organization.objects.count(), 1)

    def test_organization_post_api(self):
        path = reverse("users:organization_list")
        data = {"name": "test-org", "slug": "test-org"}
        with self.assertNumQueries(6):
            r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Organization.objects.count(), 2)

    def test_organization_detail_api(self):
        org1 = self._get_org()
        path = reverse("users:organization_detail", args=(org1.pk,))
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_organization_detail_nonsuperuser_api(self):
        user = self._create_user()
        view_perm = Permission.objects.filter(codename="view_organization")
        user.user_permissions.add(*view_perm)
        self.client.force_login(user)
        org1 = self._get_org()
        path = reverse("users:organization_detail", args=(org1.pk,))
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 404)

    def test_organization_put_api(self):
        org1 = self._get_org()
        self.assertEqual(org1.name, "test org")
        self.assertEqual(org1.description, "")
        path = reverse("users:organization_detail", args=(org1.pk,))
        data = {
            "name": "test org change",
            "is_active": False,
            "slug": "test-org-change",
            "description": "testing PUT",
            "email": "testorg@test.com",
            "url": "",
        }
        with self.assertNumQueries(8):
            r = self.client.put(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "test org change")
        self.assertEqual(r.data["description"], "testing PUT")

    def test_organization_patch_api(self):
        org1 = self._get_org()
        self.assertEqual(org1.name, "test org")
        path = reverse("users:organization_detail", args=(org1.pk,))
        data = {
            "name": "test org change",
        }
        with self.assertNumQueries(6):
            r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "test org change")

    def test_create_organization_owner_api(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        org1 = self._create_org(name="org1")
        org1_user1 = self._create_org_user(user=user1, organization=org1)
        path = reverse("users:organization_detail", args=(org1.pk,))
        data = {"owner": {"organization_user": org1_user1.pk}}
        with self.assertNumQueries(18):
            r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["owner"]["organization_user"], org1_user1.pk)

    def test_remove_organization_owner_api(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        org1 = self._create_org(name="org1")
        org1_user1 = self._create_org_user(user=user1, organization=org1)
        self._create_org_owner(organization_user=org1_user1, organization=org1)
        path = reverse("users:organization_detail", args=(org1.pk,))
        data = {"owner": {"organization_user": ""}}
        with self.assertNumQueries(12):
            r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["owner"], None)

    def test_organization_delete_api(self):
        org1 = self._create_org(name="test org 2")
        self.assertEqual(Organization.objects.count(), 2)
        path = reverse("users:organization_detail", args=(org1.pk,))
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Organization.objects.count(), 1)

    def test_get_organization_for_org_manager(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        org1 = self._create_org(name="org1")
        self._create_org_user(user=user1, organization=org1, is_admin=True)
        view_perm = Permission.objects.filter(codename="view_organization")
        user1.user_permissions.add(*view_perm)
        self.client.force_login(user1)

        with self.subTest("Organization List"):
            path = reverse("users:organization_list")
            with self.assertNumQueries(5):
                r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["count"], 1)

        with self.subTest("Organization Detail"):
            path = reverse("users:organization_detail", args=(org1.pk,))
            with self.assertNumQueries(5):
                r = self.client.get(path)
            self.assertEqual(r.status_code, 200)

    def test_change_organizationowner_for_org(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        user2 = self._create_user(username="user2", email="user2@email.com")
        org1 = self._create_org(name="org1")
        org1_user1 = self._create_org_user(user=user1, organization=org1)
        org1_user2 = self._create_org_user(user=user2, organization=org1)
        self._create_org_owner(organization_user=org1_user1, organization=org1)
        self.assertEqual(org1.owner.organization_user.id, org1_user1.id)
        path = reverse("users:organization_detail", args=(org1.pk,))
        data = {"owner": {"organization_user": org1_user2.id}}
        with self.assertNumQueries(27):
            r = self.client.patch(path, data, content_type="application/json")
        org1.refresh_from_db()
        self.assertEqual(org1.owner.organization_user.id, org1_user2.id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["owner"]["organization_user"], org1_user2.id)

    def test_orguser_filter_for_organization_detail(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        user2 = self._create_user(username="user2", email="user2@email.com")
        org1 = self._create_org(name="org1")
        org2 = self._create_org(name="org2")
        self._create_org_user(user=user1, organization=org1, is_admin=True)
        self._create_org_user(user=user2, organization=org2)
        change_perm = Permission.objects.filter(codename="change_organization")
        user1.user_permissions.add(*change_perm)
        self.client.force_login(user1)
        path = reverse("users:organization_detail", args=(org1.pk,))
        with self.assertNumQueries(6):
            r = self.client.get(path, {"format": "api"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "user1</option>")
        self.assertNotContains(r, "user2</option>")

    # Tests for Group Model API endpoints
    def test_get_group_list_403(self):
        user = self._create_user(username="user1", email="user1@email.com")
        self.client.force_login(user)
        path = reverse("users:group_list")
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 403)

    def test_get_group_list_api(self):
        path = reverse("users:group_list")
        with self.assertNumQueries(5):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 2)

    def test_create_group_list_api(self):
        path = reverse("users:group_list")
        data = {"name": "test-group", "permissions": []}
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data.pop("id"), 3)
        self.assertEqual(r.data, data)

    def test_get_group_detail_api(self):
        path = reverse("users:group_detail", args="1")
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], 1)
        self.assertEqual(r.data["name"], "Operator")
        self.assertIn("Can view organization", r.data["permissions"][0])

    def test_put_group_detail_api(self):
        path = reverse("users:group_detail", args="1")
        data = {"name": "test-Operator", "permissions": []}
        r = self.client.put(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], 1)
        self.assertEqual(r.data["name"], "test-Operator")

    def test_patch_group_detail_api(self):
        path = reverse("users:group_detail", args="1")
        data = {"permissions": [1]}
        r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.data["permissions"], ["1: emailaddress | Can add email address"]
        )

    def test_patch_group_detail_assign_permission_api(self):
        path = reverse("users:group_detail", args="1")
        grp = Group.objects.get(id=1)
        self.assertEqual(grp.permissions.values_list("codename", flat=True).count(), 1)
        data = {
            "permissions": [
                "2: emailaddress | Can change email address",
                "3: emailaddress | Can delete email address",
            ]
        }
        r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(grp.permissions.values_list("codename", flat=True).count(), 2)

    def test_delete_group_detail_api(self):
        path = reverse("users:group_detail", args="1")
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertIsNone(r.data)

    # Test Change Password endpoints
    def test_with_wrong_password(self):
        user1 = self._create_user(is_staff=True)
        self.client.force_login(user1)
        path = reverse("users:change_password", args=(user1.pk,))
        data = {"current_password": "wrong", "new_password": "super1234"}
        with self.assertNumQueries(5):
            r = self.client.put(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            r.data["current_password"][0][:],
            "Your old password was entered incorrectly. Please enter it again.",
        )

    def test_old_password_with_empty_new_password(self):
        user = self._get_user()
        path = reverse("users:change_password", args=(user.pk,))
        data = {"old_password": "tester", "new_password": ""}
        with self.assertNumQueries(4):
            response = self.client.put(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_change_password_of_superuser_by_superuser(self):
        client = auth.get_user(self.client)
        path = reverse("users:change_password", args=(client.pk,))
        data = {
            "current_password": "admin",
            "new_password": "super1234",
            "confirm_password": "super1234",
        }
        with self.assertNumQueries(5):
            r = self.client.put(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "Success")
        self.assertEqual(r.data["message"], "Password updated successfully")

    def test_change_password_of_other_user_by_superuser(self):
        user1 = self._create_user(
            username="user1233", password="tester123", email="user@test.com"
        )
        data = {
            "current_password": "wrong",
            "new_password": "change123",
            "confirm_password": "change123",
        }
        path = reverse("users:change_password", args=(user1.pk,))
        with self.assertNumQueries(5):
            r = self.client.put(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)

    def test_change_password_of_different_org_user(self):
        user2 = self._create_user(username="user2", email="user2@mail.com")
        org1 = self._create_org(name="org1")
        org1_manager = self._create_user(
            username="org1_manager", password="test123", email="org1_manager@test.com"
        )
        self._create_org_user(organization=org1, user=org1_manager, is_admin=True)
        administrator = Group.objects.get(name="Administrator")
        org1_manager.groups.add(administrator)
        self.client.force_login(org1_manager)
        path = reverse("users:change_password", args=(user2.pk,))
        data = {"old_password": "admin", "new_password": "super1234"}
        with self.assertNumQueries(7):
            response = self.client.put(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 404)

    def test_change_password_with_wrong_confirm_password(self):
        user1 = self._create_user(
            username="user1233", password="tester123", email="user@test.com"
        )
        data = {
            "current_password": "",
            "new_password": "change123",
            "confirm_password": "change321",
        }
        path = reverse("users:change_password", args=(user1.pk,))
        with self.assertNumQueries(4):
            response = self.client.put(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["confirm_password"][0],
            "The two password fields didn’t match.",
        )

    def test_change_password_with_same_old_password(self):
        client = auth.get_user(self.client)
        path = reverse("users:change_password", args=(client.pk,))
        data = {
            "current_password": "admin",
            "new_password": "admin",
            "confirm_password": "admin",
        }
        with self.assertNumQueries(4):
            response = self.client.put(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["new_password"][0]),
            "New password cannot be the same as your old password.",
        )

    def test_change_password_org_manager(self):
        # Org managers should be able to update
        # passwords of his org. users
        org1 = self._create_org(name="org1")
        org1_manager = self._create_user(
            username="org1_manager", password="test123", email="org1_manager@test.com"
        )
        self._create_org_user(organization=org1, user=org1_manager, is_admin=True)
        administrator = Group.objects.get(name="Administrator")
        org1_manager.groups.add(administrator)

        org1_user = self._create_user(
            username="org1_user",
            password="test321",
            email="org1_user@test.com",
            is_staff=True,
        )
        self._create_org_user(organization=org1, user=org1_user)
        org1_user.groups.add(administrator)

        with self.subTest("Change password of org manager by manager"):
            self.client.force_login(org1_manager)
            path = reverse("users:change_password", args=(org1_manager.pk,))
            data = {
                "current_password": "test123",
                "new_password": "test1234",
                "confirm_password": "test1234",
            }
            with self.assertNumQueries(5):
                r = self.client.put(path, data, content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["status"], "Success")
            self.assertEqual(r.data["message"], "Password updated successfully")

        with self.subTest("Change password of org user by org manager"):
            org1_manager.refresh_from_db()
            self.client.force_login(org1_manager)
            path = reverse("users:change_password", args=(org1_user.pk,))
            data = {
                "current_password": "test321",
                "new_password": "test1234",
                "confirm_password": "test1234",
            }
            with self.assertNumQueries(8):
                r = self.client.put(path, data, content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["status"], "Success")
            self.assertEqual(r.data["message"], "Password updated successfully")

        with self.subTest("change password of org user by itself"):
            org1_user.refresh_from_db()
            self.client.force_login(org1_user)
            path = reverse("users:change_password", args=(org1_user.pk,))
            data = {
                "current_password": "test1234",
                "new_password": "test1342",
                "confirm_password": "test1342",
            }
            with self.assertNumQueries(5):
                r = self.client.put(path, data, content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["status"], "Success")
            self.assertEqual(r.data["message"], "Password updated successfully")

    # Tests for users email update endpoints
    def test_get_email_list_api(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        path = reverse("users:email_list", args=(user1.pk,))
        with self.assertNumQueries(5):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0].get("email"), "user1@email.com")

    def test_post_email_list_api(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        self.assertEqual(EmailAddress.objects.filter(user=user1).count(), 1)
        path = reverse("users:email_list", args=(user1.pk,))
        data = {"email": "newemail@test.com"}
        expected_queries = 9 if django.VERSION < (5, 2) else 13
        with self.assertNumQueries(expected_queries):
            response = self.client.post(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], "newemail@test.com")
        self.assertEqual(EmailAddress.objects.filter(user=user1).count(), 2)

    def test_get_email_list_multitenancy_api(self):
        org1 = self._create_org(name="org1")
        org2 = self._create_org(name="org2")
        org1_user = self._create_user(username="org1user", email="org1user@mail.om")
        self._create_org_user(user=org1_user, organization=org1, is_admin=True)
        email_perm = Permission.objects.filter(codename__endswith="emailaddress")
        org1_user.user_permissions.add(*email_perm)
        org2_user = self._create_user(username="org2user", email="org2user@mail.om")
        self._create_org_user(user=org2_user, organization=org2)
        self.client.force_login(org1_user)
        path = reverse("users:email_list", args=(org2_user.pk,))
        with self.assertNumQueries(4):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

    def test_put_email_update_api(self):
        user1 = self._create_user(username="user2", email="user2@email.com")
        self.assertEqual(EmailAddress.objects.filter(user=user1).count(), 1)
        email_id = EmailAddress.objects.get(user=user1).id
        path = reverse("users:email_update", args=(user1.pk, email_id))
        data = {"email": "emailchange@test.com", "primary": True}
        expected_queries = 11 if django.VERSION < (5, 2) else 15
        with self.assertNumQueries(expected_queries):
            response = self.client.put(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "emailchange@test.com")

    def test_patch_email_update_api(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        email_id = EmailAddress.objects.get(user=user1).id
        path = reverse("users:email_update", args=(user1.pk, email_id))
        data = {"email": "changemail@test.com"}
        expected_queries = 11 if django.VERSION < (5, 2) else 15
        with self.assertNumQueries(expected_queries):
            response = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            EmailAddress.objects.get(user=user1).email, "changemail@test.com"
        )

    def test_delete_email_api(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        self.assertEqual(EmailAddress.objects.filter(user=user1).count(), 1)
        email_id = EmailAddress.objects.get(user=user1).id
        path = reverse("users:email_update", args=(user1.pk, email_id))
        with self.assertNumQueries(6):
            response = self.client.delete(path)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(EmailAddress.objects.filter(user=user1).count(), 0)

    # Tests for superuser's User API endpoints
    def test_get_user_list_api(self):
        path = reverse("users:user_list")
        with self.assertNumQueries(5):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)

    def test_create_user_list_api(self):
        with self.subTest("create user, standard case"):
            mail_sent = len(mail.outbox)
            self.assertEqual(User.objects.count(), 1)
            path = reverse("users:user_list")
            data = {
                "username": "tester",
                "email": "tester@test.com",
                "password": "password123",
            }
            r = self.client.post(path, data, content_type="application/json")
            self.assertEqual(r.status_code, 201)
            self.assertEqual(User.objects.count(), 2)
            self.assertEqual(r.data["groups"], [])
            self.assertEqual(r.data["organization_users"], [])
            self.assertEqual(r.data["username"], "tester")
            self.assertEqual(r.data["email"], "tester@test.com")
            self.assertEqual(r.data["is_active"], True)
            # ensure email address object is created but not verified
            user = User.objects.filter(email=data["email"]).first()
            self.assertIsNotNone(user)
            self.assertEqual(user.emailaddress_set.count(), 1)
            email = user.emailaddress_set.first()
            self.assertFalse(email.verified)
            self.assertFalse(email.primary)
            # ensure the email verification link is sent
            self.assertEqual(len(mail.outbox), mail_sent + 1)

        with self.subTest("create user and flag email as verified"):
            mail_sent = len(mail.outbox)
            User.objects.filter(email=data["email"]).delete()
            data["email_verified"] = True
            r = self.client.post(path, data, content_type="application/json")
            self.assertEqual(r.status_code, 201)
            user = User.objects.filter(email=data["email"]).first()
            self.assertIsNotNone(user)
            self.assertEqual(user.emailaddress_set.count(), 1)
            email = user.emailaddress_set.first()
            self.assertTrue(email.verified)
            self.assertTrue(email.primary)
            # ensure the email verification link is not sent
            self.assertEqual(len(mail.outbox), mail_sent)

    def test_post_with_empty_form_api_400(self):
        path = reverse("users:user_list")
        with self.assertNumQueries(1):
            r = self.client.post(path, {}, content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_create_user_with_group_org_user_api(self):
        path = reverse("users:user_list")
        org1 = self._get_org()
        data = {
            "username": "tester",
            "email": "tester@test.com",
            "password": "password",
            "groups": [1],
            "organization_users": {"is_admin": False, "organization": org1.pk},
        }
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 201)

    def test_post_with_no_email(self):
        path = reverse("users:user_list")
        data = {"username": "", "email": "", "password": ""}
        with self.assertNumQueries(1):
            r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_user_detail_no_org_user_api(self):
        user = self._get_user()
        path = reverse("users:user_detail", args=(user.pk,))
        data = {"organization_users": []}
        with self.assertNumQueries(9):
            r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)

    def test_get_user_detail_api(self):
        user = self._get_user()
        path = reverse("users:user_detail", args=(user.pk,))
        with self.assertNumQueries(5):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], str(user.id))
        self.assertEqual(r.data["email"], "test@tester.com")

    def test_put_user_detail_api(self):
        user = self._get_user()
        org1 = self._get_org()
        path = reverse("users:user_detail", args=(user.pk,))
        data = {
            "username": "tester",
            "first_name": "Tester",
            "last_name": "Tester",
            "email": "test@tester.com",
            "bio": "",
            "url": "",
            "company": "",
            "location": "",
            "phone_number": None,
            "birth_date": "1987-03-23",
            "notes": "",
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
            "groups": [],
            "user_permissions": [],
            "organization_users": [{"is_admin": False, "organization": org1.pk}],
        }
        self.assertEqual(OrganizationUser.objects.count(), 0)
        r = self.client.put(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(OrganizationUser.objects.count(), 1)
        self.assertEqual(r.data["organization_users"][0]["organization"], org1.pk)

    def test_patch_user_detail_api(self):
        user = self._get_user()
        path = reverse("users:user_detail", args=(user.pk,))
        data = {"username": "changetestuser"}
        with self.assertNumQueries(10):
            r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["username"], "changetestuser")

    def test_remove_org_user_api(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        org1 = self._create_org(name="org1")
        self._create_org_user(user=user1, organization=org1)
        path = reverse("users:user_detail", args=(user1.pk,))
        data = {"organization_users": [{"is_admin": False, "organization": org1.pk}]}
        with self.assertNumQueries(17):
            r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["organization_users"], [])

    def test_make_user_org_admin_api(self):
        user1 = self._create_user(username="user1", email="user1@email.com")
        org1 = self._create_org(name="org1")
        self._create_org_user(user=user1, organization=org1)
        path = reverse("users:user_detail", args=(user1.pk,))
        data = {"organization_users": [{"is_admin": True, "organization": org1.pk}]}
        r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["organization_users"][0]["is_admin"])

    def test_assign_user_to_groups_api(self):
        user = self._get_user()
        self.assertEqual(user.groups.count(), 0)
        path = reverse("users:user_detail", args=(user.pk,))
        data = {"groups": [1]}
        with self.assertNumQueries(13):
            r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(user.groups.count(), 1)
        self.assertEqual(r.data["groups"], [1])

    def test_assign_permission_to_user_api(self):
        user = self._get_user()
        self.assertEqual(user.get_user_permissions(), set())
        self.assertEqual(user.user_permissions.count(), 0)
        path = reverse("users:user_detail", args=(user.pk,))
        data = {"user_permissions": [1, 2]}
        with self.assertNumQueries(14):
            r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(user.user_permissions.count(), 2)
        self.assertEqual(r.data["user_permissions"], [1, 2])

    def test_delete_user_api(self):
        user = self._get_user()
        path = reverse("users:user_detail", args=(user.pk,))
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)

    def test_user_list_for_nonsuperuser_api(self):
        org1 = self._create_org(name="org1")
        org1_manager = self._create_user(
            username="org1_manager", password="test123", email="org1_manager@test.com"
        )
        self._create_org_user(organization=org1, user=org1_manager, is_admin=True)
        administrator = Group.objects.get(name="Administrator")
        org1_manager.groups.add(administrator)
        self.client.force_login(org1_manager)

        with self.subTest("test user list"):
            path = reverse("users:user_list")
            with self.assertNumQueries(9):
                r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("is_superuser", str(r.content))

        with self.subTest("test create org user"):
            self.assertEqual(User.objects.count(), 3)
            data = {
                "username": "user2org1",
                "password": "password",
                "email": "user2org1@test.com",
                "organization_users": {"is_admin": False, "organization": org1.pk},
            }
            r = self.client.post(path, data, content_type="application/json")
            self.assertEqual(r.status_code, 201)
            self.assertNotIn("is_superuser", r.data)

        with self.subTest("test user detail"):
            path = reverse("users:user_detail", args=(org1_manager.pk,))
            with self.assertNumQueries(8):
                r = self.client.get(path)
            self.assertEqual(r.status_code, 200)

        with self.subTest("test update user data"):
            path = reverse("users:user_detail", args=(org1_manager.pk,))
            data = {"username": "changetestuser"}
            with self.assertNumQueries(13):
                r = self.client.patch(path, data, content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["username"], "changetestuser")

    def test_organization_slug_post_custom_validation_api(self):
        path = reverse("users:organization_list")
        data = {"name": "test-org", "slug": "test-org"}
        with self.assertNumQueries(6):
            r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Organization.objects.count(), 2)
        # try to create a new organization with the same slug
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Organization.objects.count(), 2)
        self.assertListEqual(list(r.data.keys()), ["slug", "organization"])

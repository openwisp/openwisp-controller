from unittest import mock
from uuid import UUID

from django.test import TestCase
from django.test.utils import override_settings

from openwisp_users import settings as users_settings
from openwisp_users.backends import UsersAuthenticationBackend

from .utils import TestOrganizationMixin

auth_backend = UsersAuthenticationBackend()


class TestBackends(TestOrganizationMixin, TestCase):
    def _test_user_auth_backend_helper(self, username, password, pk):
        self.client.login(username=username, password=password)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(
            UUID(self.client.session["_auth_user_id"], version=4),
            pk,
        )
        self.client.logout()
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(
        AUTHENTICATION_BACKENDS=("openwisp_users.backends.UsersAuthenticationBackend",)
    )
    def test_user_auth_backend(self):
        user = self._create_user(
            username="tester",
            email="tester@gmail.com",
            phone_number="+237675579231",
            password="tester",
        )
        with self.subTest("Test login with username"):
            self._test_user_auth_backend_helper("tester", "tester", user.pk)

        with self.subTest("Test login with email"):
            self._test_user_auth_backend_helper("tester@gmail.com", "tester", user.pk)

        with self.subTest("Test login with phone_number"):
            self._test_user_auth_backend_helper("+237675579231", "tester", user.pk)

    @override_settings(
        AUTHENTICATION_BACKENDS=("openwisp_users.backends.UsersAuthenticationBackend",)
    )
    def test_user_with_email_as_username_auth_backend(self):
        user = self._create_user(
            username="tester",
            email="tester@gmail.com",
            phone_number="+237675579231",
            password="tester",
        )
        self._create_user(
            username="tester@gmail.com",
            email="tester1@gmail.com",
            phone_number="+237675579232",
            password="tester1",
        )
        self._test_user_auth_backend_helper(user.email, "tester", user.pk)

    @override_settings(
        AUTHENTICATION_BACKENDS=("openwisp_users.backends.UsersAuthenticationBackend",)
    )
    def test_user_with_phone_number_as_username_auth_backend(self):
        user = self._create_user(
            username="tester",
            email="tester@gmail.com",
            phone_number="+237675579231",
            password="tester",
        )
        self._create_user(
            username="+237675579231",
            email="tester1@gmail.com",
            phone_number="+237675579232",
            password="tester1",
        )
        self._test_user_auth_backend_helper(user.phone_number, "tester", user.pk)

    def test_auth_backend_get_users(self):
        user = self._create_user(
            username="tester",
            email="tester@gmail.com",
            phone_number="+237675579231",
            password="tester",
        )
        user1 = self._create_user(
            username="tester1",
            email="tester1@gmail.com",
            phone_number="+237675579232",
            password="tester1",
        )

        with self.subTest("get user with invalid identifier"):
            self.assertEqual(len(auth_backend.get_users("invalid")), 0)

        with self.subTest("get user with email"):
            user1.username = user.email
            user1.save()
            self.assertEqual(auth_backend.get_users(user.email)[0], user)

        with self.subTest("get user with phone_number"):
            user1.username = user.phone_number
            user1.save()
            self.assertEqual(auth_backend.get_users(user.phone_number)[0], user)

        with self.subTest("get user with username"):
            self.assertEqual(auth_backend.get_users(user.username)[0], user)

    @override_settings(
        AUTHENTICATION_BACKENDS=("openwisp_users.backends.UsersAuthenticationBackend",),
    )
    def test_accept_flexible_phone_number_format(self):
        user1 = self._create_user(
            username="tester1",
            email="tester1@test.com",
            phone_number="+393665243702",
            password="tester1",
        )
        variants = (
            "+39 3665243702",
            "+39 366.52.43.702",
            "+39 366.52 43-702",
        )
        for variant in variants:
            self.assertEqual(auth_backend.get_users(variant).count(), 1)
            self.assertEqual(auth_backend.get_users(variant).first(), user1)

    @override_settings(
        AUTHENTICATION_BACKENDS=("openwisp_users.backends.UsersAuthenticationBackend",),
    )
    @mock.patch.object(users_settings, "AUTH_BACKEND_AUTO_PREFIXES", ("+39",))
    def test_partial_phone_number(self):
        user1 = self._create_user(
            username="tester1",
            email="tester1@test.com",
            phone_number="+393665243702",
            password="tester1",
        )
        self.assertEqual(auth_backend.get_users("3665243702").count(), 1)
        self.assertEqual(auth_backend.get_users("3665243702").first(), user1)

        with self.subTest("test with leading zero"):
            self.assertEqual(auth_backend.get_users("03665243702").count(), 1)
            self.assertEqual(auth_backend.get_users("03665243702").first(), user1)

        with self.subTest("test different prefix which is not enabled"):
            self._create_user(
                username="tester2",
                email="tester2@test.com",
                phone_number="+51911524370",
                password="tester2",
            )
            self.assertEqual(auth_backend.get_users("911524370").count(), 0)

    @mock.patch("openwisp_users.backends.UsersAuthenticationBackend.get_users")
    def test_user_auth_without_email(self, mocked_get_users):
        self._create_user(
            username="tester",
            password="tester",
            email=None,
        )
        self.client.login(username=None, password=None)
        mocked_get_users.assert_not_called()

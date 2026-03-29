from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, modify_settings
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sesame import settings as sesame_settings
from sesame.utils import get_token as get_one_time_auth_token_for_user

from openwisp_users.api.authentication import BearerAuthentication, SesameAuthentication

from . import APITestCase

User = get_user_model()


class AuthenticationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.operator = self._create_operator()

    def test_bearer_authentication(self):
        @api_view(["GET"])
        @permission_classes([IsAuthenticated])
        @authentication_classes([BearerAuthentication])
        def my_view(request):
            return Response({})

        request = self.factory.get("/")
        response = my_view(request)
        self.assertEqual(response.status_code, 401)

        token = self._obtain_auth_token()
        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    @modify_settings(AUTHENTICATION_BACKENDS={"append": "sesame.backends.ModelBackend"})
    def test_sesame_authentication(self):
        @api_view(["GET"])
        @permission_classes([IsAuthenticated])
        @authentication_classes([SesameAuthentication])
        def my_view(request):
            return Response({})

        user = User.objects.first()
        token = get_one_time_auth_token_for_user(user)

        with self.subTest("Test without header"):
            request = self.factory.get("/")
            response = my_view(request)
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test token missing"):
            request = self.factory.get(
                "/", HTTP_AUTHORIZATION=f"{sesame_settings.TOKEN_NAME}"
            )
            response = my_view(request)
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test extra key"):
            request = self.factory.get(
                "/", HTTP_AUTHORIZATION=f"{sesame_settings.TOKEN_NAME} {token} extrakey"
            )
            response = my_view(request)
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test UnicodeError"):
            request = self.factory.get(
                "/", HTTP_AUTHORIZATION=f'{sesame_settings.TOKEN_NAME} "¸"'
            )
            response = my_view(request)
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test with invalid token"):
            request = self.factory.get(
                "/", HTTP_AUTHORIZATION=f"{sesame_settings.TOKEN_NAME} token"
            )
            response = my_view(request)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(str(response.data["detail"]), "Invalid or expired token.")

        with self.subTest("Test ideal flow"):
            request = self.factory.get(
                "/", HTTP_AUTHORIZATION=f"{sesame_settings.TOKEN_NAME} {token}"
            )
            response = my_view(request)
            self.assertEqual(response.status_code, 200)

from django.utils.translation import gettext as _
from rest_framework import exceptions
from rest_framework.authentication import (
    BaseAuthentication,
    TokenAuthentication,
    get_authorization_header,
)
from sesame import settings as sesame_settings
from sesame.utils import get_token as get_one_time_auth_token_for_user  # noqa
from sesame.utils import get_user as get_user_from_one_time_auth_token


class BearerAuthentication(TokenAuthentication):
    keyword = "Bearer"


class SesameAuthentication(BaseAuthentication):
    keyword = sesame_settings.TOKEN_NAME

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            msg = _("Invalid token header. No credentials provided.")
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = _("Invalid token header. Token string should not contain spaces.")
            raise exceptions.AuthenticationFailed(msg)

        try:
            token = auth[1].decode()
        except UnicodeError:
            msg = _(
                "Invalid token header. "
                "Token string should not contain invalid characters."
            )
            raise exceptions.AuthenticationFailed(msg)

        return self.authenticate_credentials(token)

    def authenticate_credentials(self, key):
        user = get_user_from_one_time_auth_token(key)
        if user is None:
            raise exceptions.AuthenticationFailed(_("Invalid or expired token."))
        return (user, key)

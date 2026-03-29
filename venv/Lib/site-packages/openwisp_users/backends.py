import phonenumbers
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from phonenumbers.phonenumberutil import NumberParseException

from . import settings as app_settings

User = get_user_model()


class UsersAuthenticationBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Only proceed if a username is provided. Other auth backends may attempt
        # authentication without a username; returning early here avoids querying
        # the database with a `None` username, which can be inefficient.
        if not username:
            return
        for user in self.get_users(username):
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

    def get_users(self, identifier):
        conditions = Q(email=identifier) | Q(username=identifier)
        # if the identifier is a phone number, use the phone number as primary condition
        for phone_number in self._get_phone_numbers(identifier):
            conditions = Q(phone_number=phone_number) | conditions
        return User.objects.filter(conditions)

    def _get_phone_numbers(self, identifier):
        prefixes = [""] + list(app_settings.AUTH_BACKEND_AUTO_PREFIXES)
        numbers = [identifier]
        found = []
        # support those countries which use
        # leading zeros for their local numbers
        if str(identifier).startswith("0"):
            numbers.append(identifier[1:])
        for prefix in prefixes:
            for number in numbers:
                value = f"{prefix}{number}"
                try:
                    phonenumbers.parse(value)
                    found.append(value)
                except NumberParseException:
                    continue
        return found

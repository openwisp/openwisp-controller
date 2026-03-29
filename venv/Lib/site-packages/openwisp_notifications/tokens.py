from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class EmailTokenGenerator(PasswordResetTokenGenerator):
    """
    Email token generator that extends the default PasswordResetTokenGenerator
    without a fixed expiry period.
    """

    key_salt = "openwisp_notifications.tokens.EmailTokenGenerator"

    def check_token(self, user, token):
        """
        Check that a token is correct for a given user.
        """
        if not (user and token):
            return False

        # Parse the token
        try:
            ts_b36, _ = token.split("-")
        except ValueError:
            return False

        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        # Check that the timestamp/uid has not been tampered with
        if hasattr(self, "secret_fallbacks"):
            # For newer Django versions
            for secret in [self.secret, *self.secret_fallbacks]:
                if constant_time_compare(
                    self._make_token_with_timestamp(user, ts, secret),
                    token,
                ):
                    return True
        else:
            # For older Django versions
            if constant_time_compare(self._make_token_with_timestamp(user, ts), token):
                return True

        return False

    def _make_hash_value(self, user, timestamp):
        """
        Hash the user's primary key and password to produce a token that is
        invalidated when the password is reset.
        """
        email_field = user.get_email_field_name()
        email = getattr(user, email_field, "") or ""
        return f"{user.pk}{user.password}{timestamp}{email}"


email_token_generator = EmailTokenGenerator()

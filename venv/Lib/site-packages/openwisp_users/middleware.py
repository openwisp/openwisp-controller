from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import redirect
from django.urls import resolve, reverse_lazy
from django.utils.translation import gettext_lazy as _


class PasswordExpirationMiddleware:
    exempted_url_names = [
        "account_change_password",
        "admin:logout",
        "account_logout",
        "account_reset_password",
        "account_reset_password_done",
        "account_reset_password_from_key",
        "account_reset_password_from_key_done",
    ]
    admin_login_path = reverse_lazy("admin:login")
    admin_index_path = reverse_lazy("admin:index")
    account_change_password_path = reverse_lazy("account_change_password")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Check if the user is authenticated and their password has expired
        if (
            request.user.is_authenticated
            and request.user.has_password_expired()
            # We use `resolve()` here to get the `url_name` from the `request.path`.
            # This is more flexible than using `reverse()` as it doesn't require
            # passing arguments to get the correct path.
            and resolve(request.path).url_name not in self.exempted_url_names
        ):
            messages.warning(
                request,
                _("Your password has expired, please update your password."),
            )
            redirect_path = self.account_change_password_path
            if request.user.is_staff:
                next_path = (
                    request.path
                    if request.path != self.admin_login_path
                    else self.admin_index_path
                )
                redirect_path = f"{redirect_path}?{REDIRECT_FIELD_NAME}={next_path}"
            return redirect(redirect_path)
        return response

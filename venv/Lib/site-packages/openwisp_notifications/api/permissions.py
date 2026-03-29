from rest_framework.permissions import BasePermission


class PreferencesPermission(BasePermission):
    """
    Permission class for the notification preferences.

    Permission is granted only in these two cases:
    1. Superusers can change the notification preferences of any user.
    2. Regular users can only change their own preferences.
    """

    def has_permission(self, request, view):
        return request.user.is_superuser or request.user.id == view.kwargs.get(
            "user_id"
        )

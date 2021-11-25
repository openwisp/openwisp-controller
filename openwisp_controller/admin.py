"""
Base admin classes and mixins
"""
from django.core.exceptions import PermissionDenied

from openwisp_users.multitenancy import (
    MultitenantAdminMixin as BaseMultitenantAdminMixin,
)


class OrgVersionMixin(object):
    """
    Base VersionAdmin for openwisp_controller
    """

    def recoverlist_view(self, request, extra_context=None):
        """only superusers are allowed to recover deleted objects"""
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().recoverlist_view(request, extra_context)


class MultitenantAdminMixin(OrgVersionMixin, BaseMultitenantAdminMixin):
    """
    openwisp_utils.admin.MultitenantAdminMixin + OrgVersionMixin
    """

    pass

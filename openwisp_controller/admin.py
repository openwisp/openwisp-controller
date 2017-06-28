"""
Base admin classes and mixins
"""
from django.core.exceptions import PermissionDenied

from openwisp_utils.admin import MultitenantAdminMixin as BaseMultitenantAdminMixin


class OrgVersionMixin(object):
    """
    Base VersionAdmin for openwisp_controller
    """
    def recoverlist_view(self, request, extra_context=None):
        """ only superusers are allowed to recover deleted objects """
        if not request.user.is_superuser:
            raise PermissionDenied
        return super(OrgVersionMixin, self).recoverlist_view(request, extra_context)


class MultitenantAdminMixin(OrgVersionMixin, BaseMultitenantAdminMixin):
    """
    openwisp_utils.admin.MultitenantAdminMixin + OrgVersionMixin
    """
    pass


class AlwaysHasChangedMixin(object):
    def has_changed(self):
        """
        This django-admin trick ensures the settings
        are saved even if default values are unchanged
        (without this trick new setting objects won't be
        created unless users change the default values)
        """
        if self.instance._state.adding:
            return True
        return super(AlwaysHasChangedMixin, self).has_changed()

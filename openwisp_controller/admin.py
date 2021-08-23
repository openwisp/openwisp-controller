"""
Base admin classes and mixins
"""
from django.contrib.admin.widgets import AutocompleteSelect
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _

from openwisp_users.multitenancy import (
    MultitenantAdminMixin as BaseMultitenantAdminMixin,
)


class OrgVersionMixin(object):
    """
    Base VersionAdmin for openwisp_controller
    """

    def recoverlist_view(self, request, extra_context=None):
        """ only superusers are allowed to recover deleted objects """
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().recoverlist_view(request, extra_context)


class MultitenantAutocompleteSelect(AutocompleteSelect):
    select2_placeholder = _('Shared systemwide (no organization)')

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        attrs['data-placeholder'] = self.select2_placeholder
        return attrs


class MultitenantAdminMixin(OrgVersionMixin, BaseMultitenantAdminMixin):
    """
    openwisp_utils.admin.MultitenantAdminMixin + OrgVersionMixin
    """

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if (
            db_field.name == 'organization'
            and 'organization' in self.get_autocomplete_fields(request)
        ):
            kwargs['widget'] = MultitenantAutocompleteSelect(
                db_field.remote_field, self.admin_site, using=kwargs.get('using')
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

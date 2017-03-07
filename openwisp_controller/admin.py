"""
Base admin classes and mixins
"""
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _


class OrgVersionMixin(object):
    """
    Base VersionAdmin for openwisp_controller
    """
    def recoverlist_view(self, request, extra_context=None):
        """ only superusers are allowed to recover deleted objects """
        if not request.user.is_superuser:
            raise PermissionDenied
        return super(OrgVersionMixin, self).recoverlist_view(request, extra_context)


class MultitenantAdminMixin(OrgVersionMixin):
    """
    Mixin that makes a ModelAdmin class multitenant:
    users will see only the objects related to the organizations
    they are associated with.
    """
    multitenant_shared_relations = []

    def get_repr(self, obj):
        return str(obj)

    get_repr.short_description = _('name')

    def get_queryset(self, request):
        """
        if current user is not superuser, show only the
        objects associated to organizations she's associated with
        """
        qs = super(MultitenantAdminMixin, self).get_queryset(request)
        if request.user.is_superuser:
            return qs
        organizations = request.user.organizations_pk
        return qs.filter(organization__in=organizations)

    def get_form(self, request, obj=None, **kwargs):
        """
        if current user is not superuser:
            * show only relevant organizations
            * show only relations associated to relevant organizations
              or shared relations
        """
        form = super(MultitenantAdminMixin, self).get_form(request, obj, **kwargs)
        fields = form.base_fields
        if not request.user.is_superuser:
            orgs_pk = request.user.organizations_pk
            # organizations relation;
            # may be readonly and not present in field list
            if 'organization' in fields:
                org_field = fields['organization']
                org_field.queryset = org_field.queryset.filter(pk__in=orgs_pk)
            # other relations
            q = Q(organization__in=orgs_pk) | Q(organization=None)
            for field_name in self.multitenant_shared_relations:
                # each relation may be readonly
                # and not present in field list
                if field_name not in fields:
                    continue
                field = fields[field_name]
                field.queryset = field.queryset.filter(q)
        return form


class MultitenantOrgFilter(admin.RelatedFieldListFilter):
    """
    Admin filter that shows only organizations the current
    user is associated with in its available choices
    """
    def field_choices(self, field, request, model_admin):
        if request.user.is_superuser:
            return super(MultitenantOrgFilter, self).field_choices(field, request, model_admin)
        organizations = request.user.organizations_pk
        return field.get_choices(include_blank=False,
                                 limit_choices_to={'pk__in': organizations})

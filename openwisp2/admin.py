"""
Base admin classes and mixins
"""
from django.contrib import admin
from django.db.models import Q


class MultitenantAdminMixin(object):
    """
    Mixin that makes a ModelAdmin class multitenant:
    users will see only the objects related to the organizations
    they are associated with.
    """
    multitenant_shared_relations = []

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
        if not request.user.is_superuser:
            orgs_pk = request.user.organizations_pk
            # organizations
            org_field = form.base_fields['organization']
            org_field.queryset = org_field.queryset.filter(pk__in=orgs_pk)
            # other relations
            q = Q(organization__in=orgs_pk) | Q(organization=None)
            for field_name in self.multitenant_shared_relations:
                field = form.base_fields[field_name]
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

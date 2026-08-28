from django.apps import apps
from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q
from django_x509.base.admin import AbstractCaAdmin, AbstractCertAdmin
from reversion.admin import VersionAdmin
from swapper import load_model

from openwisp_users.multitenancy import MultitenantOrgFilter

from ..admin import MultitenantAdminMixin

Ca = load_model("django_x509", "Ca")
Cert = load_model("django_x509", "Cert")


class SharedRelationAutocompleteMixin:
    def _source_allows_shared_relation(self, request):
        match = getattr(request, "resolver_match", None)
        if getattr(match, "view_name", None) != "admin:autocomplete":
            return False
        app_label = request.GET.get("app_label")
        model_name = request.GET.get("model_name")
        field_name = request.GET.get("field_name")
        if not all([app_label, model_name, field_name]):
            return False
        try:
            source_model = apps.get_model(app_label, model_name)
            source_field = source_model._meta.get_field(field_name)
        except (LookupError, FieldDoesNotExist):
            return False
        if getattr(source_field.remote_field, "model", None) != self.model:
            return False
        source_admin = self.admin_site._registry.get(source_model)
        if not source_admin or not source_admin.has_view_permission(request):
            return False
        if field_name not in getattr(source_admin, "autocomplete_fields", ()):
            return False
        shared_relations = getattr(source_admin, "multitenant_shared_relations", ())
        return field_name in shared_relations

    def _get_unscoped_queryset(self, request):
        qs = self.model._default_manager.get_queryset()
        ordering = self.get_ordering(request) or (self.model._meta.pk.name,)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self._source_allows_shared_relation(request):
            qs = self._get_unscoped_queryset(request)
            if request.user.is_superuser:
                return qs
            orgs = request.user.organizations_managed
            return qs.filter(Q(organization__in=orgs) | Q(organization=None))
        return qs


@admin.register(Ca)
class CaAdmin(
    SharedRelationAutocompleteMixin,
    MultitenantAdminMixin,
    AbstractCaAdmin,
    VersionAdmin,
):
    history_latest_first = True


CaAdmin.fields.insert(2, "organization")
CaAdmin.list_filter.insert(0, MultitenantOrgFilter)
CaAdmin.list_display.insert(1, "organization")
CaAdmin.Media.js += ("admin/pki/js/show-org-field.js",)


@admin.register(Cert)
class CertAdmin(
    SharedRelationAutocompleteMixin,
    MultitenantAdminMixin,
    AbstractCertAdmin,
    VersionAdmin,
):
    multitenant_shared_relations = ("ca",)
    history_latest_first = True


CertAdmin.fields.insert(2, "organization")
CertAdmin.list_filter.insert(0, MultitenantOrgFilter)
CertAdmin.list_filter.remove("ca")
CertAdmin.list_display.insert(1, "organization")
CertAdmin.Media.js += ("admin/pki/js/show-org-field.js",)

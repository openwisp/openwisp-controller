from django.contrib import admin, messages
from django.contrib.admin import action
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from django_x509.base.admin import AbstractCaAdmin, AbstractCertAdmin
from reversion.admin import VersionAdmin
from swapper import load_model

from openwisp_users.multitenancy import MultitenantOrgFilter

from ..admin import MultitenantAdminMixin

Ca = load_model("django_x509", "Ca")
Cert = load_model("django_x509", "Cert")


def _exclude_disabled_org(self, request, queryset):
    allowed = queryset.filter(
        Q(organization__isnull=True) | Q(organization__is_active=True)
    )
    skipped = queryset.exclude(
        Q(organization__isnull=True) | Q(organization__is_active=True)
    ).count()
    if skipped:
        self.message_user(
            request,
            ngettext_lazy(
                "%(count)d item belonging to a disabled organization was skipped.",
                "%(count)d items belonging to a disabled organization were skipped.",
                skipped,
            )
            % {"count": skipped},
            level=messages.WARNING,
        )
    return allowed


@admin.register(Ca)
class CaAdmin(MultitenantAdminMixin, AbstractCaAdmin, VersionAdmin):
    history_latest_first = True

    @action(description=_("Renew selected CAs"), permissions=["change"])
    def renew_ca(self, request, queryset):
        queryset = _exclude_disabled_org(self, request, queryset)
        return super().renew_ca(request, queryset)


CaAdmin.fields.insert(2, "organization")
CaAdmin.list_filter.insert(0, MultitenantOrgFilter)
CaAdmin.list_display.insert(1, "organization")
CaAdmin.Media.js += ("admin/pki/js/show-org-field.js",)


@admin.register(Cert)
class CertAdmin(MultitenantAdminMixin, AbstractCertAdmin, VersionAdmin):
    multitenant_shared_relations = ("ca",)
    history_latest_first = True

    @action(description=_("Renew selected certificates"), permissions=["change"])
    def renew_cert(self, request, queryset):
        queryset = _exclude_disabled_org(self, request, queryset)
        return super().renew_cert(request, queryset)

    @action(description=_("Revoke selected certificates"), permissions=["change"])
    def revoke_action(self, request, queryset):
        queryset = _exclude_disabled_org(self, request, queryset)
        return super().revoke_action(request, queryset)


CertAdmin.fields.insert(2, "organization")
CertAdmin.list_filter.insert(0, MultitenantOrgFilter)
CertAdmin.list_filter.remove("ca")
CertAdmin.list_display.insert(1, "organization")
CertAdmin.Media.js += ("admin/pki/js/show-org-field.js",)

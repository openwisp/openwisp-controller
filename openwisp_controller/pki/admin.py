from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django_x509.base.admin import AbstractCaAdmin, AbstractCertAdmin
from reversion.admin import VersionAdmin
from swapper import load_model

from openwisp_users.multitenancy import MultitenantOrgFilter

from ..admin import MultitenantAdminMixin

Ca = load_model("django_x509", "Ca")
Cert = load_model("django_x509", "Cert")


def _cert_in_use_message(cert):
    """Returns a message if ``cert`` is in use by a VPN, otherwise ``None``.

    Deleting a certificate that is still assigned to a VPN client cascades
    the deletion of the client and leaves the device configuration in a
    corrupted state (issue #1419), so deletion is blocked from the admin.
    """
    VpnClient = load_model("config", "VpnClient")
    Vpn = load_model("config", "Vpn")
    vpn_client = (
        VpnClient.objects.filter(cert=cert).select_related("config__device").first()
    )
    if vpn_client:
        device = vpn_client.config.device
        return _(
            'the certificate "%(cert)s" is currently used by the device '
            '"%(device)s"; remove the VPN template from the device before '
            "deleting this certificate."
        ) % {"cert": cert, "device": device}
    vpn = Vpn.objects.filter(cert=cert).first()
    if vpn:
        return _(
            'the certificate "%(cert)s" is currently used by the VPN server '
            '"%(vpn)s"; change the VPN certificate before deleting this one.'
        ) % {"cert": cert, "vpn": vpn}
    return None


def _ca_in_use_message(ca):
    """Returns a message if ``ca`` is in use by a VPN, otherwise ``None``."""
    VpnClient = load_model("config", "VpnClient")
    Vpn = load_model("config", "Vpn")
    vpn = Vpn.objects.filter(ca=ca).first()
    if vpn:
        return _(
            'the CA "%(ca)s" is currently used by the VPN server "%(vpn)s"; '
            "change the VPN CA before deleting this one."
        ) % {"ca": ca, "vpn": vpn}
    vpn_client = (
        VpnClient.objects.filter(cert__ca=ca).select_related("config__device").first()
    )
    if vpn_client:
        device = vpn_client.config.device
        return _(
            'the CA "%(ca)s" issued a certificate used by the device '
            '"%(device)s"; remove the VPN template from the device before '
            "deleting this CA."
        ) % {"ca": ca, "device": device}
    return None


@admin.register(Ca)
class CaAdmin(MultitenantAdminMixin, AbstractCaAdmin, VersionAdmin):
    history_latest_first = True

    def get_deleted_objects(self, objs, request):
        deletable, model_count, perms_needed, protected = super().get_deleted_objects(
            objs, request
        )
        protected = list(protected)
        for ca in objs:
            message = _ca_in_use_message(ca)
            if message:
                protected.append(message)
        return deletable, model_count, perms_needed, protected


CaAdmin.fields.insert(2, "organization")
CaAdmin.list_filter.insert(0, MultitenantOrgFilter)
CaAdmin.list_display.insert(1, "organization")
CaAdmin.Media.js += ("admin/pki/js/show-org-field.js",)


@admin.register(Cert)
class CertAdmin(MultitenantAdminMixin, AbstractCertAdmin, VersionAdmin):
    multitenant_shared_relations = ("ca",)
    history_latest_first = True

    def get_deleted_objects(self, objs, request):
        deletable, model_count, perms_needed, protected = super().get_deleted_objects(
            objs, request
        )
        protected = list(protected)
        for cert in objs:
            message = _cert_in_use_message(cert)
            if message:
                protected.append(message)
        return deletable, model_count, perms_needed, protected


CertAdmin.fields.insert(2, "organization")
CertAdmin.list_filter.insert(0, MultitenantOrgFilter)
CertAdmin.list_filter.remove("ca")
CertAdmin.list_display.insert(1, "organization")
CertAdmin.Media.js += ("admin/pki/js/show-org-field.js",)

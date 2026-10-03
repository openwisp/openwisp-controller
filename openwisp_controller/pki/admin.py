from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django_x509.base.admin import AbstractCaAdmin, AbstractCertAdmin
from reversion.admin import VersionAdmin
from swapper import load_model

from openwisp_users.multitenancy import MultitenantOrgFilter

from ..admin import MultitenantAdminMixin

Ca = load_model("django_x509", "Ca")
Cert = load_model("django_x509", "Cert")


@admin.register(Ca)
class CaAdmin(MultitenantAdminMixin, AbstractCaAdmin, VersionAdmin):
    history_latest_first = True

    def get_deleted_objects(self, objs, request, *args, **kwargs):
        to_delete, model_count, perms_needed, protected = super().get_deleted_objects(
            objs, request, *args, **kwargs
        )
        protected = list(protected)
        ca_ids = [ca.pk for ca in objs]
        if not ca_ids:
            return to_delete, model_count, perms_needed, protected

        VpnClient = load_model("config", "VpnClient")
        Vpn = load_model("config", "Vpn")

        vpns = Vpn.objects.filter(ca_id__in=ca_ids).select_related("ca")
        for vpn in vpns:
            msg = _(
                'The CA "%(ca)s" is currently used by the VPN server '
                '"%(vpn)s"; change the VPN CA before deleting this one.'
            ) % {"ca": vpn.ca, "vpn": vpn}
            if msg not in protected:
                protected.append(msg)

        vpn_clients = VpnClient.objects.filter(cert__ca_id__in=ca_ids).select_related(
            "cert__ca", "config__device"
        )
        for client in vpn_clients:
            device = (
                client.config.device
                if hasattr(client.config, "device")
                else client.config
            )
            msg = _(
                'The CA "%(ca)s" issued a certificate used by the device '
                '"%(device)s"; remove the VPN template from the device '
                "before deleting this CA."
            ) % {"ca": client.cert.ca, "device": device}
            if msg not in protected:
                protected.append(msg)

        return to_delete, model_count, perms_needed, protected


CaAdmin.fields.insert(2, "organization")
CaAdmin.list_filter.insert(0, MultitenantOrgFilter)
CaAdmin.list_display.insert(1, "organization")
CaAdmin.Media.js += ("admin/pki/js/show-org-field.js",)


@admin.register(Cert)
class CertAdmin(MultitenantAdminMixin, AbstractCertAdmin, VersionAdmin):
    multitenant_shared_relations = ("ca",)
    history_latest_first = True

    def get_deleted_objects(self, objs, request, *args, **kwargs):
        to_delete, model_count, perms_needed, protected = super().get_deleted_objects(
            objs, request, *args, **kwargs
        )
        protected = list(protected)
        cert_ids = [cert.pk for cert in objs]
        if not cert_ids:
            return to_delete, model_count, perms_needed, protected

        VpnClient = load_model("config", "VpnClient")
        Vpn = load_model("config", "Vpn")

        vpn_clients = VpnClient.objects.filter(cert_id__in=cert_ids).select_related(
            "cert", "config__device"
        )
        for client in vpn_clients:
            device = (
                client.config.device
                if hasattr(client.config, "device")
                else client.config
            )
            msg = _(
                'The certificate "%(cert)s" is currently used by the device '
                '"%(device)s"; remove the VPN template from the device '
                "before deleting this certificate."
            ) % {"cert": client.cert, "device": device}
            if msg not in protected:
                protected.append(msg)

        vpns = Vpn.objects.filter(cert_id__in=cert_ids).select_related("cert")
        for vpn in vpns:
            msg = _(
                'The certificate "%(cert)s" is currently used by the VPN '
                'server "%(vpn)s"; change the VPN certificate before '
                "deleting this one."
            ) % {"cert": vpn.cert, "vpn": vpn}
            if msg not in protected:
                protected.append(msg)

        return to_delete, model_count, perms_needed, protected


CertAdmin.fields.insert(2, "organization")
CertAdmin.list_filter.insert(0, MultitenantOrgFilter)
CertAdmin.list_filter.remove("ca")
CertAdmin.list_display.insert(1, "organization")
CertAdmin.Media.js += ("admin/pki/js/show-org-field.js",)

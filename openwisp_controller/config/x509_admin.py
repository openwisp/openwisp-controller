from urllib.parse import urlencode

from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_utils.admin_theme.filters import AutocompleteFilter

Config = load_model("config", "Config")
Device = load_model("config", "Device")
DeviceCertificate = load_model("config", "DeviceCertificate")


class DeviceCertificateDeviceFilter(AutocompleteFilter):
    """
    Filters the X.509 certificate changelist by the owning device.

    This lives in config because it follows DeviceCertificate relations. Config
    registers it on CertAdmin so the X.509 app remains independent of config.
    """

    title = _("device")
    field_name = "device"
    parameter_name = "devicecertificate__config__device"
    rel_model = Config

    def __init__(self, request, params, model, model_admin):
        """Limits selected device labels to devices visible to the user."""
        self._request = request
        self._device_admin = model_admin.admin_site._registry[Device]
        super().__init__(request, params, model, model_admin)

    def get_autocomplete_url(self, request, model_admin):
        """Returns the built-in admin autocomplete endpoint."""
        return reverse("admin:autocomplete")

    def get_queryset_for_field(self, model, name):
        """Returns the multitenancy-filtered queryset for selected labels."""
        return self._device_admin.get_queryset(self._request)


def register_cert_admin_filter():
    """Registers the config-owned device filter on the X.509 certificate admin."""
    from openwisp_controller.pki.admin import CertAdmin

    if DeviceCertificateDeviceFilter not in CertAdmin.list_filter:
        CertAdmin.list_filter.insert(1, DeviceCertificateDeviceFilter)


def get_device_certificate_changelist_url(device_id):
    """Builds the certificate changelist URL filtered by device."""
    cert_model = DeviceCertificate.cert.field.related_model
    changelist_url = reverse(
        f"admin:{cert_model._meta.app_label}_{cert_model._meta.model_name}_changelist"
    )
    return (
        f"{changelist_url}?"
        f"{urlencode({DeviceCertificateDeviceFilter.parameter_name: str(device_id)})}"
    )


def get_device_certificate_details(config):
    """Renders the standalone certificate details table for a configuration."""
    qs = (
        DeviceCertificate.objects.filter(config=config)
        .select_related("cert__ca", "template")
        .order_by("created")[:51]
    )
    cert_data = []
    for dc in qs:
        template_app = dc.template._meta.app_label
        template_model = dc.template._meta.model_name
        template_url = reverse(
            f"admin:{template_app}_{template_model}_change",
            args=[dc.template.id],
        )
        if dc.cert:
            app_label = dc.cert._meta.app_label
            model_name = dc.cert._meta.model_name
            url = reverse(f"admin:{app_label}_{model_name}_change", args=[dc.cert.id])
            ca_url = None
            if dc.cert.ca:
                ca_app = dc.cert.ca._meta.app_label
                ca_model = dc.cert.ca._meta.model_name
                ca_url = reverse(
                    f"admin:{ca_app}_{ca_model}_change", args=[dc.cert.ca.id]
                )
            key_length_display = dc.cert.key_length
            if hasattr(dc.cert, "get_key_length_display"):
                key_length_display = dc.cert.get_key_length_display()
            cert_data.append(
                {
                    "template_name": dc.template.name,
                    "template_url": template_url,
                    "common_name": dc.cert.common_name,
                    "ca_name": dc.cert.ca.name if dc.cert.ca else "-",
                    "ca_url": ca_url,
                    "key_length_display": key_length_display,
                    "digest": dc.cert.digest,
                    "created": dc.cert.created,
                    "validity_end": dc.cert.validity_end,
                    "is_revoked": dc.cert.revoked,
                    "url": url,
                    "has_cert": True,
                }
            )
        else:
            cert_data.append(
                {
                    "template_name": dc.template.name,
                    "template_url": template_url,
                    "has_cert": False,
                }
            )
    has_more = len(cert_data) > 50
    if has_more:
        cert_data = cert_data[:50]
    return render_to_string(
        "admin/config/device_certificates_table.html",
        {
            "certificates": cert_data,
            "has_more": has_more,
            "cert_list_url": get_device_certificate_changelist_url(config.device_id),
        },
    )

import logging

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from openwisp_notifications.signals import notify
from swapper import get_model_name, load_model

from openwisp_controller.config import settings as app_settings
from openwisp_controller.config.utils import (
    copy_ca_attributes,
    generate_common_name,
    get_client_extensions,
    revoke_device_cert,
)
from openwisp_utils.base import TimeStampedEditableModel

logger = logging.getLogger(__name__)

MAC_ADDRESS_OID = "1.3.6.1.4.1.65901.1"
DEVICE_UUID_OID = "1.3.6.1.4.1.65901.2"


class AbstractDeviceCertificate(TimeStampedEditableModel):
    config = models.ForeignKey(
        get_model_name("config", "Config"), on_delete=models.CASCADE
    )
    template = models.ForeignKey(
        get_model_name("config", "Template"), on_delete=models.CASCADE
    )
    cert = models.OneToOneField(
        get_model_name("django_x509", "Cert"),
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    auto_cert = models.BooleanField(default=False)

    class Meta:
        abstract = True
        unique_together = ("config", "template")
        verbose_name = _("Device certificate")
        verbose_name_plural = _("Device certificates")

    def __str__(self):
        cert_name = self.cert.name if self.cert else str(_("Pending Generation"))
        return f"{self.config.device.name} - {cert_name}"

    def clean(self):
        Template = load_model("config", "Template")
        if (
            self.cert_id
            and Template.objects.filter(blueprint_cert_id=self.cert_id).exists()
        ):
            raise ValidationError(
                {
                    "cert": _(
                        "This certificate is currently used as a blueprint "
                        "by a template and cannot be directly assigned to a device."
                    )
                }
            )
        super().clean()

    def save(self, *args, **kwargs):
        """Performs automatic provisioning if ``auto_cert`` is True."""
        with transaction.atomic():
            if self.auto_cert and not self.cert:
                self._auto_x509()
            self.full_clean(validate_unique=False)
            super().save(*args, **kwargs)

    def _auto_x509(self):
        """
        Automatically creates an x509 certificate.
        """
        if self.cert:
            return
        cn = self._get_common_name()
        self._auto_create_cert(name=self.config.device.name, common_name=cn)

    def _get_common_name(self):
        """
        Returns the common name for a new certificate.
        """
        return generate_common_name(self.config.device)

    def _build_cert(self, name, common_name):
        """Build (but do not save) a Cert instance from template + blueprint."""
        ca = self.template.ca
        blueprint = self.template.blueprint_cert
        cert_model = self.__class__.cert.field.related_model

        attrs = copy_ca_attributes(ca, blueprint)
        extensions = get_client_extensions(
            blueprint, hardware_oids=self._get_hardware_oid_extensions()
        )
        cert = cert_model(
            name=name,
            ca=ca,
            common_name=common_name,
            extensions=extensions,
            **attrs,
        )
        return self._auto_create_cert_extra(cert)

    def _get_hardware_oid_extensions(self):
        device = self.config.device
        return [
            {
                "oid": MAC_ADDRESS_OID,
                "value": f"ASN1:UTF8:string:{device.mac_address}",
                "critical": False,
            },
            {
                "oid": DEVICE_UUID_OID,
                "value": f"ASN1:UTF8:string:{device.id}",
                "critical": False,
            },
        ]

    def _auto_create_cert(self, name, common_name):
        """
        Automatically creates and assigns a client x509 certificate
        """
        cert = self._build_cert(name=name, common_name=common_name)
        cert.full_clean()
        cert.save()
        self.cert = cert
        return cert

    def _auto_create_cert_extra(self, cert):
        """
        Sets the organization on the created client certificate.
        """
        cert.organization = self.config.device.organization
        return cert

    @classmethod
    def active_auto_certs_for(cls, device):
        return cls.objects.filter(
            config__device=device,
            auto_cert=True,
            cert__revoked=False,
            template__type="cert",
        )

    @classmethod
    def post_delete(cls, instance, **kwargs):
        """
        Receiver of ``post_delete`` signal.
        Automatically revokes the certificate when the template is unassigned.
        """
        revoke_device_cert(instance)

    @classmethod
    def regenerate_certificates(cls, device_id, expected_cert_ids=None):
        """
        Revokes stale certificates and mints fresh ones when
        device identity fields change.
        """
        if not app_settings.REGENERATE_CERTS_ON_HARDWARE_CHANGE:
            return
        Device = load_model("config", "Device")
        try:
            device = Device.objects.get(id=device_id)
        except Device.DoesNotExist:
            return

        configs_to_update = set()
        certs_regenerated = 0

        with transaction.atomic():
            qs = cls.active_auto_certs_for(device).select_for_update()
            if expected_cert_ids:
                valid_cert_ids = [cert_id for _dc_id, cert_id in expected_cert_ids]
                qs = qs.filter(cert_id__in=valid_cert_ids)
            active_device_certs = qs.select_related("cert", "config", "template")
            if not active_device_certs.exists():
                return
            expected_map = dict(expected_cert_ids) if expected_cert_ids else {}
            for dc in active_device_certs:
                expected_cert_id = expected_map.get(dc.id)
                if expected_cert_id is not None and dc.cert_id != expected_cert_id:
                    continue
                old_cert = dc.cert
                old_cert.revoke()
                new_cert = dc._build_cert(
                    name=device.name, common_name=dc._get_common_name()
                )
                new_cert.full_clean()
                new_cert.save()
                dc.cert = new_cert
                dc.save()
                configs_to_update.add(dc.config)
                certs_regenerated += 1
        for config in configs_to_update:
            config.refresh_from_db()
            config.update_status_if_checksum_changed()
        if certs_regenerated > 0:
            try:
                message = _(
                    "Device identity fields changed on device {device_name}. "
                    "Successfully regenerated {certs_regenerated} "
                    "bound X.509 certificate(s)."
                ).format(
                    device_name=str(device.name),
                    certs_regenerated=certs_regenerated,
                )
                notify.send(
                    sender=device,
                    target=device,
                    action_object=device,
                    type="generic_message",
                    verb=_("device identity fields changed"),
                    message=message,
                    level="info",
                )
            except Exception as e:
                logger.warning(
                    f"Could not push regeneration notification for {device.name}: {e}"
                )

import copy

import shortuuid
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name, load_model

from openwisp_controller.config import settings as app_settings
from openwisp_utils.base import TimeStampedEditableModel

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
        Returns a unique common name for a new certificate, mirroring VPN client logic.
        """
        d = self.config.device
        end = 63 - len(d.mac_address)
        truncated_name = d.name[:end]
        unique_slug = shortuuid.ShortUUID().random(length=8)
        cn_format = app_settings.COMMON_NAME_FORMAT
        if cn_format == "{mac_address}-{name}" and truncated_name == d.mac_address:
            cn_format = "{mac_address}"
        format_dict = {**d.__dict__, "name": truncated_name}
        common_name = cn_format.format(**format_dict)[:55]
        common_name = f"{common_name}-{unique_slug}"
        return common_name

    def _build_cert(self, name, common_name):
        """Build (but do not save) a Cert instance from template + blueprint."""
        ca = self.template.ca
        blueprint = self.template.blueprint_cert
        cert_model = self.__class__.cert.field.related_model

        attrs = self._clone_blueprint_attrs(ca, blueprint)
        extensions = self._build_extensions(blueprint)
        cert = cert_model(
            name=name,
            ca=ca,
            common_name=common_name,
            extensions=extensions,
            **attrs,
        )
        return self._auto_create_cert_extra(cert)

    def _clone_blueprint_attrs(self, ca, blueprint):
        """
        Extracts base X.509 attributes (such as key length, digest, and
        location data) from the provided blueprint certificate.
        """
        source = blueprint or ca
        digest = str(source.digest) if not blueprint else source.digest
        return dict(
            key_length=source.key_length,
            digest=digest,
            country_code=source.country_code,
            state=source.state,
            city=source.city,
            organization_name=source.organization_name,
            organizational_unit_name=source.organizational_unit_name,
            email=source.email,
        )

    def _build_extensions(self, blueprint):
        """Compiles the list of X.509 extensions for the new certificate."""
        if blueprint and blueprint.extensions:
            extensions = copy.deepcopy(blueprint.extensions)
        else:
            extensions = [{"name": "nsCertType", "value": "client", "critical": False}]
        extensions.extend(self._get_hardware_oid_extensions())
        return extensions

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
    def post_delete(cls, instance, **kwargs):
        """
        Receiver of ``post_delete`` signal.
        Automatically revokes the certificate when the template is unassigned.
        """
        try:
            if instance.cert and instance.auto_cert:
                instance.cert.revoke()
        except ObjectDoesNotExist:
            pass

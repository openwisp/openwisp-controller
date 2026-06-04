import copy

import shortuuid
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name, load_model

from openwisp_controller.config import settings as app_settings
from openwisp_utils.base import TimeStampedEditableModel


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

    def _auto_create_cert(self, name, common_name):
        """
        Automatically creates and assigns a client x509 certificate
        using Blueprint cloning and custom hardware OID injection.
        """
        ca = self.template.ca
        blueprint = self.template.blueprint_cert
        device = self.config.device
        cert_model = self.__class__.cert.field.related_model

        # blueprint property cloning with CA fallback
        key_length = blueprint.key_length if blueprint else ca.key_length
        digest = blueprint.digest if blueprint else str(ca.digest)
        country_code = blueprint.country_code if blueprint else ca.country_code
        state = blueprint.state if blueprint else ca.state
        city = blueprint.city if blueprint else ca.city
        organization_name = (
            blueprint.organization_name if blueprint else ca.organization_name
        )
        email = blueprint.email if blueprint else ca.email

        if blueprint and blueprint.extensions:
            extensions = copy.deepcopy(blueprint.extensions)
        else:
            extensions = [{"name": "nsCertType", "value": "client", "critical": False}]

        # inject MAC and UUID as custom OIDs, prerequisite: #228 in django-x509
        mac_oid = "1.3.6.1.4.1.65901.1"
        uuid_oid = "1.3.6.1.4.1.65901.2"
        extensions.extend(
            [
                {
                    "oid": mac_oid,
                    "value": f"ASN1:UTF8:string:{device.mac_address}",
                    "critical": False,
                },
                {
                    "oid": uuid_oid,
                    "value": f"ASN1:UTF8:string:{device.id}",
                    "critical": False,
                },
            ]
        )
        cert = cert_model(
            name=name,
            ca=ca,
            key_length=key_length,
            digest=digest,
            country_code=country_code,
            state=state,
            city=city,
            organization_name=organization_name,
            email=email,
            common_name=common_name,
            extensions=extensions,
        )
        cert = self._auto_create_cert_extra(cert)
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

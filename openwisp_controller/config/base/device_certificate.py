from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name, load_model


class AbstractDeviceCertificate(models.Model):
    config = models.ForeignKey(
        get_model_name("config", "Config"), on_delete=models.CASCADE
    )
    template = models.ForeignKey(
        get_model_name("config", "Template"), on_delete=models.CASCADE
    )
    cert = models.OneToOneField(
        get_model_name("django_x509", "Cert"), on_delete=models.CASCADE
    )
    auto_cert = models.BooleanField(default=False)

    class Meta:
        abstract = True
        unique_together = ("config", "template")
        verbose_name = _("Device certificate")
        verbose_name_plural = _("Device certificates")

    def __str__(self):
        return f"{self.config.device.name} - {self.cert.name}"

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

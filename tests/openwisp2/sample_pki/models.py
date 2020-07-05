from django.db import models

from openwisp_controller.pki.base.models import AbstractCa, AbstractCert


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        abstract = True


class Ca(DetailsModel, AbstractCa):
    class Meta(AbstractCa.Meta):
        abstract = False


class Cert(DetailsModel, AbstractCert):
    class Meta(AbstractCert.Meta):
        abstract = False

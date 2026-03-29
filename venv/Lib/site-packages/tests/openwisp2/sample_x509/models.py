from django.db import models

from django_x509.base.models import AbstractCa, AbstractCert


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        abstract = True


class Ca(DetailsModel, AbstractCa):
    """
    Concrete Ca model
    """

    class Meta(AbstractCa.Meta):
        abstract = False


class Cert(DetailsModel, AbstractCert):
    """
    Concrete Cert model
    """

    class Meta(AbstractCert.Meta):
        abstract = False


class CustomCert(DetailsModel, AbstractCert):
    """
    Custom Cert model
    """

    fingerprint = models.CharField(primary_key=True, max_length=64, unique=True)

    class Meta(AbstractCert.Meta):
        abstract = False

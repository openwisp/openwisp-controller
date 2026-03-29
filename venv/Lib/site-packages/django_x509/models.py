import swapper

from .base.models import AbstractCa, AbstractCert


class Ca(AbstractCa):
    """
    Concrete Ca model
    """

    class Meta(AbstractCa.Meta):
        abstract = False
        swappable = swapper.swappable_setting("django_x509", "Ca")


class Cert(AbstractCert):
    """
    Concrete Cert model
    """

    class Meta(AbstractCert.Meta):
        abstract = False
        swappable = swapper.swappable_setting("django_x509", "Cert")

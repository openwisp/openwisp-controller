from django.db import models
from django.utils.translation import ugettext_lazy as _

from django_x509.base.models import AbstractCa, AbstractCert

from ..models import ValidateOrgMixin


class Ca(AbstractCa):
    """
    OpenWISP2 CA model
    """
    organization = models.ForeignKey('organizations.Organization',
                                     verbose_name=_('organization'),
                                     blank=True,
                                     null=True)

    class Meta(AbstractCa.Meta):
        abstract = False


class Cert(ValidateOrgMixin, AbstractCert):
    """
    OpenWISP2 cert model
    """
    ca = models.ForeignKey(Ca, verbose_name=_('CA'))
    organization = models.ForeignKey('organizations.Organization',
                                     verbose_name=_('organization'),
                                     blank=True,
                                     null=True)

    class Meta(AbstractCert.Meta):
        abstract = False

    def clean(self):
        self._validate_org_relation('ca')


Ca.Meta.abstract = False

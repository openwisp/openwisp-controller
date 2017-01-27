from django.db import models
from django.utils.translation import ugettext_lazy as _

from django_x509.base.models import AbstractCa, AbstractCert

from ..models import ShareableOrgMixin


class Ca(ShareableOrgMixin, AbstractCa):
    """
    OpenWISP2 CA model
    """


class Cert(ShareableOrgMixin, AbstractCert):
    """
    OpenWISP2 cert model
    """
    ca = models.ForeignKey(Ca, verbose_name=_('CA'))

    def clean(self):
        self._validate_org_relation('ca')

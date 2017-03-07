from django.db import models
from django.utils.translation import ugettext_lazy as _

from django_x509.base.models import AbstractCa, AbstractCert
from openwisp_users.mixins import ShareableOrgMixin


class Ca(ShareableOrgMixin, AbstractCa):
    """
    openwisp-controller CA model
    """
    class Meta(AbstractCa.Meta):
        abstract = False


class Cert(ShareableOrgMixin, AbstractCert):
    """
    openwisp-controller cert model
    """
    ca = models.ForeignKey(Ca, verbose_name=_('CA'))

    class Meta(AbstractCert.Meta):
        abstract = False

    def clean(self):
        self._validate_org_relation('ca')

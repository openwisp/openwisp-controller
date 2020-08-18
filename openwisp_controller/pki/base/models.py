from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_x509.base.models import AbstractCa as BaseCa
from django_x509.base.models import AbstractCert as BaseCert
from swapper import get_model_name

from openwisp_users.mixins import ShareableOrgMixin


class AbstractCa(ShareableOrgMixin, BaseCa):
    class Meta(BaseCa.Meta):
        abstract = True


class AbstractCert(ShareableOrgMixin, BaseCert):

    ca = models.ForeignKey(
        get_model_name('django_x509', 'Ca'),
        verbose_name=_('CA'),
        on_delete=models.CASCADE,
    )

    class Meta(BaseCert.Meta):
        abstract = True

    def clean(self):
        self._validate_org_relation('ca')

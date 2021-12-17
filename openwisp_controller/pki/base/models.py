from django.db import models
from django.utils.translation import gettext_lazy as _
from django_x509.base.models import AbstractCa as BaseCa
from django_x509.base.models import AbstractCert as BaseCert
from swapper import get_model_name

from openwisp_users.mixins import ShareableOrgMixin

from ..utils import UnqiueCommonNameMixin


class AbstractCa(ShareableOrgMixin, UnqiueCommonNameMixin, BaseCa):
    class Meta(BaseCa.Meta):
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=['common_name', 'organization'],
                name='%(app_label)s_%(class)s_comman_name_and_organization_is_unique',
            ),
        ]


class AbstractCert(ShareableOrgMixin, UnqiueCommonNameMixin, BaseCert):

    ca = models.ForeignKey(
        get_model_name('django_x509', 'Ca'),
        verbose_name=_('CA'),
        on_delete=models.CASCADE,
    )

    class Meta(BaseCert.Meta):
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=['common_name', 'organization'],
                name='%(app_label)s_%(class)s_comman_name_and_organization_is_unique',
            ),
        ]

    def clean(self):
        self._validate_org_relation('ca')

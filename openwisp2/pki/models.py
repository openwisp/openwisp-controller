from django.db import models
from django.utils.translation import ugettext_lazy as _

from django_x509.base.models import AbstractCa


class Ca(AbstractCa):
    """
    OpenWISP2 CA model
    """
    organization = models.ForeignKey('organizations.Organization',
                                     verbose_name=_('organization'),
                                     blank=True,
                                     null=True)


Ca.Meta.abstract = False

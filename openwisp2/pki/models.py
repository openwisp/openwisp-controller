from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _

from django_x509.base.models import AbstractCa, AbstractCert


class Ca(AbstractCa):
    """
    OpenWISP2 CA model
    """
    organization = models.ForeignKey('organizations.Organization',
                                     verbose_name=_('organization'),
                                     blank=True,
                                     null=True)


Ca.Meta.abstract = False


class Cert(AbstractCert):
    """
    OpenWISP2 cert model
    """
    ca = models.ForeignKey(Ca, verbose_name=_('CA'))
    organization = models.ForeignKey('organizations.Organization',
                                     verbose_name=_('organization'))

    def clean(self):
        # if CA is owned by a specific organizations, certificates
        # signed with it must also be owned by the same organization
        if self.ca.organization_id and self.organization_id != self.ca.organization_id:
            message = _('Please ensure that the organization of this certificate '
                        'and the organization of the related CA match.')
            raise ValidationError({'organization': message})


Ca.Meta.abstract = False

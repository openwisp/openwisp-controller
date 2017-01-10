from django.db import models
from django.utils.translation import ugettext_lazy as _
from sortedm2m.fields import SortedManyToManyField

from django_netjsonconfig.base.config import AbstractConfig, TemplatesVpnMixin
from django_netjsonconfig.base.template import AbstractTemplate
from django_netjsonconfig.base.vpn import AbstractVpn, AbstractVpnClient

from ..models import OrgMixin, ShareableOrgMixin


class Config(OrgMixin, TemplatesVpnMixin, AbstractConfig):
    """
    Concrete Config model
    """
    templates = SortedManyToManyField('config.Template',
                                      related_name='config_relations',
                                      verbose_name=_('templates'),
                                      blank=True,
                                      help_text=_('configuration templates, applied from'
                                                  'first to last'))
    vpn = models.ManyToManyField('config.Vpn',
                                 through='config.VpnClient',
                                 related_name='vpn_relations',
                                 blank=True)

    class Meta(AbstractConfig.Meta):
        abstract = False


class Template(ShareableOrgMixin, AbstractTemplate):
    """
    OpenWISP2 Template model
    """
    vpn = models.ForeignKey('config.Vpn',
                            verbose_name=_('VPN'),
                            blank=True,
                            null=True)

    def clean(self):
        self._validate_org_relation('vpn')

    class Meta(AbstractTemplate.Meta):
        abstract = False


class Vpn(ShareableOrgMixin, AbstractVpn):
    """
    OpenWISP2 VPN model
    """
    ca = models.ForeignKey('pki.Ca', verbose_name=_('Certification Authority'))
    cert = models.ForeignKey('pki.Cert',
                             verbose_name=_('x509 Certificate'),
                             help_text=_('leave blank to create automatically'),
                             blank=True,
                             null=True)

    def clean(self):
        self._validate_org_relation('ca')
        self._validate_org_relation('cert')

    class Meta(AbstractVpn.Meta):
        abstract = False


class VpnClient(AbstractVpnClient):
    """
    m2m through model
    """
    config = models.ForeignKey('config.Config',
                               on_delete=models.CASCADE)
    vpn = models.ForeignKey('config.Vpn',
                            on_delete=models.CASCADE)
    cert = models.OneToOneField('pki.Cert',
                                on_delete=models.CASCADE,
                                blank=True,
                                null=True)

    class Meta(AbstractVpnClient.Meta):
        abstract = False

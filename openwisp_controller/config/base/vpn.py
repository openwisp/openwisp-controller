import subprocess

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from swapper import get_model_name

from openwisp_users.mixins import ShareableOrgMixin
from openwisp_utils.base import KeyField

from .. import settings as app_settings
from ..tasks import create_vpn_dh
from .base import BaseConfig


class AbstractVpn(ShareableOrgMixin, BaseConfig):
    """
    Abstract VPN model
    """

    host = models.CharField(
        max_length=64, help_text=_('VPN server hostname or ip address')
    )
    ca = models.ForeignKey(
        get_model_name('django_x509', 'Ca'),
        verbose_name=_('Certification Authority'),
        on_delete=models.CASCADE,
    )
    cert = models.ForeignKey(
        get_model_name('django_x509', 'Cert'),
        verbose_name=_('x509 Certificate'),
        help_text=_('leave blank to create automatically'),
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    key = KeyField(db_index=True)
    backend = models.CharField(
        _('VPN backend'),
        choices=app_settings.VPN_BACKENDS,
        max_length=128,
        help_text=_('Select VPN configuration backend'),
    )
    notes = models.TextField(blank=True)
    # diffie hellman parameters are required
    # in some VPN solutions (eg: OpenVPN)
    dh = models.TextField(blank=True)
    # placeholder DH used as default
    # (a new one is generated in the background
    # because it can take some time)
    _placeholder_dh = (
        '-----BEGIN DH PARAMETERS-----\n'
        'MIIBCAKCAQEA1eYGbpFmXaXNhkoWbx+hrGKh8XMaiGSH45QsnMx/AOPtVfRQTTs0\n'
        '0rXgllizgqGP7Ug04+ULK5mxY1xGcm/Sh8s21I4t/HFJzElMmhRVy4B1r3bETzHi\n'
        '7DCUsK2EPi0csofnD5upwu5T6RbBAq0/HTWR/AoW2em5JS1ZhX4JV32nH33EWkl1\n'
        'PzhjVKENl9RQ/DKd+T2edUJU0r1miBqw0Xulf/LVYvwOimcp0WmYtkBJOgf9xEEP\n'
        '3Hd2KG4Ib/vR7v2Z1fdyUgB8dMAElZ2+tK5PM9E9lJmll0fsfrKtcYpgL2mk24vO\n'
        'BbOcwKkB+eBE/B9jqmbG5YYhDo9fQGmNEwIBAg==\n'
        '-----END DH PARAMETERS-----\n'
    )

    __vpn__ = True

    class Meta:
        verbose_name = _('VPN server')
        verbose_name_plural = _('VPN servers')
        abstract = True

    def clean(self, *args, **kwargs):
        """
        * ensure certificate matches CA
        """
        super().clean(*args, **kwargs)
        # certificate must be related to CA
        if self.cert and self.cert.ca.pk != self.ca.pk:
            msg = _('The selected certificate must match the selected CA.')
            raise ValidationError({'cert': msg})
        self._validate_org_relation('ca')
        self._validate_org_relation('cert')

    def save(self, *args, **kwargs):
        """
        Calls _auto_create_cert() if cert is not set
        """
        if not self.cert:
            self.cert = self._auto_create_cert()
        if not self.dh:
            self.dh = self._placeholder_dh
        is_adding = self._state.adding
        super().save(*args, **kwargs)
        if is_adding and self.dh == self._placeholder_dh:
            transaction.on_commit(lambda: create_vpn_dh.delay(self.id))

    @classmethod
    def dhparam(cls, length):
        """
        Returns an automatically generated set of DH parameters in PEM
        """
        return subprocess.check_output(  # pragma: nocover
            'openssl dhparam {0} 2> /dev/null'.format(length), shell=True
        ).decode('utf-8')

    def _auto_create_cert(self):
        """
        Automatically generates server x509 certificate
        """
        common_name = slugify(self.name)
        server_extensions = [
            {'name': 'nsCertType', 'value': 'server', 'critical': False}
        ]
        cert_model = self.__class__.cert.field.related_model
        cert = cert_model(
            name=self.name,
            ca=self.ca,
            key_length=self.ca.key_length,
            digest=self.ca.digest,
            country_code=self.ca.country_code,
            state=self.ca.state,
            city=self.ca.city,
            organization_name=self.ca.organization_name,
            email=self.ca.email,
            common_name=common_name,
            extensions=server_extensions,
        )
        cert = self._auto_create_cert_extra(cert)
        cert.save()
        return cert

    def get_context(self):
        """
        prepares context for netjsonconfig VPN backend
        """
        try:
            c = {'ca': self.ca.certificate}
        except ObjectDoesNotExist:
            c = {}
        if self.cert:
            c.update({'cert': self.cert.certificate, 'key': self.cert.private_key})
        if self.dh:
            c.update({'dh': self.dh})
        c.update(super().get_context())
        return c

    def get_system_context(self):
        return self.get_context()

    def _get_auto_context_keys(self):
        """
        returns a dictionary which indicates the names of
        the configuration variables needed to access:
            * path to CA file
            * CA certificate in PEM format
            * path to cert file
            * cert in PEM format
            * path to key file
            * key in PEM format
        """
        pk = self.pk.hex
        return {
            'ca_path': 'ca_path_{0}'.format(pk),
            'ca_contents': 'ca_contents_{0}'.format(pk),
            'cert_path': 'cert_path_{0}'.format(pk),
            'cert_contents': 'cert_contents_{0}'.format(pk),
            'key_path': 'key_path_{0}'.format(pk),
            'key_contents': 'key_contents_{0}'.format(pk),
        }

    def auto_client(self, auto_cert=True):
        """
        calls backend ``auto_client`` method and returns a configuration
        dictionary that is suitable to be used as a template
        if ``auto_cert`` is ``False`` the resulting configuration
        won't include autogenerated key and certificate details
        """
        config = {}
        backend = self.backend_class
        if hasattr(backend, 'auto_client'):
            context_keys = self._get_auto_context_keys()
            # add curly brackets for netjsonconfig context evaluation
            for key in context_keys.keys():
                context_keys[key] = '{{%s}}' % context_keys[key]
            # do not include cert and key if auto_cert is False
            if not auto_cert:
                for key in ['cert_path', 'cert_contents', 'key_path', 'key_contents']:
                    del context_keys[key]
            conifg_dict_key = self.backend_class.__name__.lower()
            auto = backend.auto_client(
                host=self.host, server=self.config[conifg_dict_key][0], **context_keys
            )
            config.update(auto)
        return config

    def _auto_create_cert_extra(self, cert):
        """
        sets the organization on the created client certificate
        """
        cert.organization = self.organization
        return cert


class AbstractVpnClient(models.Model):
    """
    m2m through model
    """

    config = models.ForeignKey(
        get_model_name('config', 'Config'), on_delete=models.CASCADE
    )
    vpn = models.ForeignKey(get_model_name('config', 'Vpn'), on_delete=models.CASCADE)
    cert = models.OneToOneField(
        get_model_name('django_x509', 'Cert'),
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    # this flags indicates whether the certificate must be
    # automatically managed, which is going to be almost in all cases
    auto_cert = models.BooleanField(default=False)

    class Meta:
        abstract = True
        unique_together = ('config', 'vpn')
        verbose_name = _('VPN client')
        verbose_name_plural = _('VPN clients')

    def save(self, *args, **kwargs):
        """
        automatically creates an x509 certificate when ``auto_cert`` is True
        """
        if self.auto_cert:
            cn = self._get_common_name()
            self._auto_create_cert(name=self.config.device.name, common_name=cn)
        super().save(*args, **kwargs)

    def _get_common_name(self):
        """
        returns the common name for a new certificate
        """
        d = self.config.device
        end = 63 - len(d.mac_address)
        d.name = d.name[:end]
        cn_format = app_settings.COMMON_NAME_FORMAT
        if cn_format == '{mac_address}-{name}' and d.name == d.mac_address:
            cn_format = '{mac_address}'
        return cn_format.format(**d.__dict__)

    @classmethod
    def post_delete(cls, **kwargs):
        """
        class method for ``post_delete`` signal
        automatically deletes certificates when ``auto_cert`` is ``True``
        """
        instance = kwargs['instance']
        if instance.auto_cert:
            instance.cert.delete()

    def _auto_create_cert_extra(self, cert):
        """
        sets the organization on the created client certificate
        """
        cert.organization = self.config.device.organization
        return cert

    def _auto_create_cert(self, name, common_name):
        """
        Automatically creates and assigns a client x509 certificate
        """
        server_extensions = [
            {'name': 'nsCertType', 'value': 'client', 'critical': False}
        ]
        ca = self.vpn.ca
        cert_model = self.__class__.cert.field.related_model
        cert = cert_model(
            name=name,
            ca=ca,
            key_length=ca.key_length,
            digest=str(ca.digest),
            country_code=ca.country_code,
            state=ca.state,
            city=ca.city,
            organization_name=ca.organization_name,
            email=ca.email,
            common_name=common_name,
            extensions=server_extensions,
        )
        cert = self._auto_create_cert_extra(cert)
        cert.full_clean()
        cert.save()
        self.cert = cert
        return cert

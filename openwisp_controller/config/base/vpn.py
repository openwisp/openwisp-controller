import collections
import ipaddress
import json
import logging
import subprocess

import shortuuid
from cache_memoize import cache_memoize
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name

from openwisp_utils.base import KeyField

from ...base import ShareableOrgMixinUniqueName
from .. import crypto
from .. import settings as app_settings
from ..signals import vpn_peers_changed, vpn_server_modified
from ..tasks import create_vpn_dh, trigger_vpn_server_endpoint
from .base import BaseConfig

logger = logging.getLogger(__name__)


def _peer_cache_key(vpn):
    """used to generate a unique cache key"""
    return str(vpn.pk)


class AbstractVpn(ShareableOrgMixinUniqueName, BaseConfig):
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
        blank=True,
        null=True,
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
    # optional, needed for VPNs which do not support automatic IP allocation
    subnet = models.ForeignKey(
        get_model_name('openwisp_ipam', 'Subnet'),
        verbose_name=_('Subnet'),
        help_text=_('Subnet IP addresses used by VPN clients, if applicable'),
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    ip = models.ForeignKey(
        get_model_name('openwisp_ipam', 'IpAddress'),
        verbose_name=_('Internal IP'),
        help_text=_('Internal IP address of the VPN server interface, if applicable'),
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    # optional, helpful for updating WireGuard and VXLAN server configuration
    webhook_endpoint = models.CharField(
        verbose_name=_('Webhook Endpoint'),
        help_text=_(
            'Webhook to trigger for updating server configuration '
            '(e.g. https://openwisp2.mydomain.com:8081/trigger-update)'
        ),
        max_length=128,
        blank=True,
        null=True,
    )
    auth_token = models.CharField(
        verbose_name=_('Webhook AuthToken'),
        help_text=_('Authentication token for triggering "Webhook Endpoint"'),
        max_length=128,
        blank=True,
        null=True,
    )
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
    # needed for wireguard
    public_key = models.CharField(blank=True, max_length=44)
    private_key = models.CharField(blank=True, max_length=44)

    __vpn__ = True

    # cache wireguard / vxlan peers for 7 days (generation is expensive)
    _PEER_CACHE_TIMEOUT = 60 * 60 * 24 * 7

    class Meta:
        verbose_name = _('VPN server')
        verbose_name_plural = _('VPN servers')
        unique_together = ('organization', 'name')
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # for internal usage
        self._send_vpn_modified_after_save = False

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        self._validate_backend()
        self._validate_certs()
        self._validate_keys()
        self._validate_org_relation('ca')
        self._validate_org_relation('cert')
        self._validate_org_relation('subnet')
        self._validate_subnet_ip()

    def _validate_backend(self):
        if self._state.adding:
            return
        if (
            'backend' not in self.get_deferred_fields()
            and self._meta.model.objects.only('backend').get(id=self.id).backend
            != self.backend
            and self.vpnclient_set.exists()
        ):
            raise ValidationError(
                {
                    'backend': _(
                        'Backend cannot be changed because the VPN is currently in use.'
                    )
                }
            )

    def _validate_certs(self):
        if not self._is_backend_type('openvpn'):
            self.ca = None
            self.cert = None
            return

        if not self.ca:
            raise ValidationError({'ca': _('CA is required with this VPN backend')})
        # certificate must be related to CA
        if self.cert and self.cert.ca.pk != self.ca.pk:
            msg = _('The selected certificate must match the selected CA.')
            raise ValidationError({'cert': msg})

    def _validate_keys(self):
        if not self._is_backend_type('wireguard'):
            self.public_key = ''
            self.private_key = ''

    def _validate_subnet_ip(self):
        if self._is_backend_type('openvpn'):
            self.subnet = None
            self.ip = None
        elif self._is_backend_type('wireguard'):
            if not self.subnet:
                raise ValidationError(
                    {'subnet': _('Subnet is required for this VPN backend.')}
                )
            if self.ip and self.ip.subnet != self.subnet:
                raise ValidationError(
                    {'ip': _('VPN IP address must be within the VPN subnet')}
                )

    def save(self, *args, **kwargs):
        """
        Calls _auto_create_cert() if cert is not set
        """
        created = self._state.adding
        if not created:
            self._check_changes()
        create_dh = False
        if not self.cert and self.ca:
            self.cert = self._auto_create_cert()
        if self._is_backend_type('openvpn') and not self.dh:
            self.dh = self._placeholder_dh
            create_dh = True
        if self._is_backend_type('wireguard'):
            self._generate_wireguard_keys()
        if self.subnet and not self.ip:
            self.ip = self._auto_create_ip()
        super().save(*args, **kwargs)
        if create_dh:
            transaction.on_commit(lambda: create_vpn_dh.delay(self.id))
        if not created and self._send_vpn_modified_after_save:
            self._send_vpn_modified_signal()
            self._send_vpn_modified_after_save = False
        self.update_vpn_server_configuration()

    def _check_changes(self):
        attrs = [
            'config',
            'host',
            'ca',
            'cert',
            'key',
            'backend',
            'subnet',
            'ip',
            'dh',
            'public_key',
            'private_key',
        ]
        current = self._meta.model.objects.only(*attrs).get(pk=self.pk)
        for attr in attrs:
            if getattr(self, attr) == getattr(current, attr):
                continue
            self._send_vpn_modified_after_save = True
            break

    def _send_vpn_modified_signal(self):
        vpn_server_modified.send(sender=self.__class__, instance=self)

    @classmethod
    def dhparam(cls, length):
        """
        Returns an automatically generated set of DH parameters in PEM
        """
        return subprocess.check_output(  # pragma: nocover
            'openssl dhparam {0} 2> /dev/null'.format(length), shell=True
        ).decode('utf-8')

    def update_vpn_server_configuration(instance, **kwargs):
        if not instance._is_backend_type('wireguard'):
            return
        if instance.webhook_endpoint and instance.auth_token:
            transaction.on_commit(
                lambda: trigger_vpn_server_endpoint.delay(
                    endpoint=instance.webhook_endpoint,
                    auth_token=instance.auth_token,
                    vpn_id=instance.pk,
                )
            )
        else:
            logger.info(
                f'Cannot update configuration of {instance.name} VPN server, '
                'webhook endpoint and authentication token are empty.'
            )

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

    def _auto_create_ip(self):
        """
        Automatically generates host IP address
        """
        return self.subnet.request_ip()

    def get_context(self):
        """
        prepares context for netjsonconfig VPN backend
        """
        c = collections.OrderedDict()
        if self.ca:
            try:
                c['ca'] = self.ca.certificate
            except ObjectDoesNotExist:
                pass
        if self.cert:
            c['cert'] = self.cert.certificate
            c['key'] = self.cert.private_key
        if self.dh:
            c['dh'] = self.dh
        if self.private_key:
            c['private_key'] = self.private_key
        if self.public_key:
            c['public_key'] = self.public_key
        if self.subnet:
            c['subnet'] = str(self.subnet.subnet)
            c['subnet_prefixlen'] = str(self.subnet.subnet.prefixlen)
        if self.ip:
            c['ip_address'] = self.ip.ip_address
        c.update(sorted(super().get_context().items()))
        return c

    def get_vpn_server_context(self):
        context = {}
        context_keys = self._get_auto_context_keys()
        if self.host:
            context[context_keys['vpn_host']] = self.host
        if self._is_backend_type('wireguard'):
            context[context_keys['vpn_port']] = self.config['wireguard'][0]['port']
        if self.ca:
            ca = self.ca
            # CA
            ca_filename = 'ca-{0}-{1}.pem'.format(
                ca.pk, ca.common_name.replace(' ', '_')
            )
            ca_path = '{0}/{1}'.format(app_settings.CERT_PATH, ca_filename)
            context.update(
                {
                    context_keys['ca_path']: ca_path,
                    context_keys['ca_contents']: ca.certificate,
                }
            )
        if self.public_key:
            context[context_keys['public_key']] = self.public_key
        if self.ip:
            context[context_keys['server_ip_address']] = self.ip.ip_address
            context[
                context_keys['server_ip_network']
            ] = f'{self.ip.ip_address}/{self.subnet.subnet.max_prefixlen}'
        return context

    def get_system_context(self):
        return self.get_context()

    def _is_backend_type(self, backend_type):
        """
        returns true if the backend path used converted to lowercase
        contains ``backend_type``.
        Checking for the exact path may not be the best choices
        given backends can be extended and customized.
        By using this method, customizations will just have
        to maintain the naming consistent.
        """
        return backend_type.lower() in self.backend.lower()

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
        WireGuard:
            * public key
            * ip address
        VXLAN:
            * vni (VXLAN Network Identifier)
        """
        pk = self.pk.hex
        context_keys = {
            'vpn_host': 'vpn_host_{}'.format(pk),
            'vpn_port': 'vpn_port_{}'.format(pk),
        }
        if self._is_backend_type('openvpn'):
            context_keys.update(
                {
                    'ca_path': 'ca_path_{0}'.format(pk),
                    'ca_contents': 'ca_contents_{0}'.format(pk),
                    'cert_path': 'cert_path_{0}'.format(pk),
                    'cert_contents': 'cert_contents_{0}'.format(pk),
                    'key_path': 'key_path_{0}'.format(pk),
                    'key_contents': 'key_contents_{0}'.format(pk),
                }
            )
        if self._is_backend_type('wireguard'):
            context_keys.update(
                {
                    'public_key': 'public_key_{}'.format(pk),
                    'ip_address': 'ip_address_{}'.format(pk),
                    'private_key': 'pvt_key_{}'.format(pk),
                }
            )
        if self._is_backend_type('vxlan'):
            context_keys.update({'vni': 'vni_{}'.format(pk)})
        if self.ip:
            context_keys.update(
                {
                    'server_ip_address': 'server_ip_address_{}'.format(pk),
                    'server_ip_network': 'server_ip_network_{}'.format(pk),
                }
            )
        return context_keys

    def auto_client(self, auto_cert=True, template_backend_class=None):
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
            config_dict_key = self.backend_class.__name__.lower()
            vpn_host = context_keys.pop('vpn_host', self.host)
            if self._is_backend_type('wireguard') and template_backend_class:
                vpn_auto_client = '{}wireguard_auto_client'.format(
                    'vxlan_' if self._is_backend_type('vxlan') else ''
                )
                auto = getattr(template_backend_class, vpn_auto_client)(
                    host=vpn_host,
                    server=self.config['wireguard'][0],
                    **context_keys,
                )
            else:
                del context_keys['vpn_port']
                auto = backend.auto_client(
                    host=self.host,
                    server=self.config[config_dict_key][0],
                    **context_keys,
                )
            config.update(auto)
        return config

    def _auto_create_cert_extra(self, cert):
        """
        sets the organization on the created client certificate
        """
        cert.organization = self.organization
        return cert

    def _generate_wireguard_keys(self):
        """
        generates wireguard private and public keys
        and set the respctive attributes
        """
        if not self.private_key or not self.public_key:
            self.private_key, self.public_key = crypto.generate_wireguard_keys()

    def get_config(self):
        config = super().get_config()
        if self._is_backend_type('wireguard'):
            self._add_wireguard(config)
        if self._is_backend_type('vxlan'):
            self._add_vxlan(config)
        return config

    def _invalidate_peer_cache(self, update=False):
        """
        Invalidates peer cache, if update=True is passed,
        the peer cache will be regenerated
        """
        if self._is_backend_type('wireguard'):
            self._get_wireguard_peers.invalidate(self)
            if update:
                self._get_wireguard_peers()
        if self._is_backend_type('vxlan'):
            self._get_vxlan_peers.invalidate(self)
            if update:
                self._get_vxlan_peers()
        # Send signal for peers changed
        vpn_peers_changed.send(sender=self.__class__, instance=self)

    def _get_peer_queryset(self):
        """
        returns an iterator to iterate over tunnel peers
        used to generate the list of peers of a tunnel (WireGuard/VXLAN)
        """
        return (
            self.vpnclient_set.select_related('config', 'ip')
            .filter(auto_cert=True)
            .only(
                'id',
                'vpn_id',
                'vni',
                'public_key',
                'config__device_id',
                'config__status',
                'ip__ip_address',
            )
            .iterator()
        )

    def _add_wireguard(self, config):
        """
        Adds wireguard peers and private key to the generated
        configuration without the need of manual intervention.
        Modifies the config data structure as a side effect.
        """
        try:
            config['wireguard'][0].setdefault('peers', [])
        except (KeyError, IndexError):
            # this error will be handled by
            # schema validation in subsequent steps
            return config
        # private key is added to the config automatically
        config['wireguard'][0]['private_key'] = self.private_key
        # peers are also added automatically (and cached)
        config['wireguard'][0]['peers'] = self._get_wireguard_peers()
        # internal IP address of wireguard interface
        config['wireguard'][0]['address'] = '{{ ip_address }}/{{ subnet_prefixlen }}'

    @cache_memoize(_PEER_CACHE_TIMEOUT, args_rewrite=_peer_cache_key)
    def _get_wireguard_peers(self):
        """
        Returns list of wireguard peers, the result is cached.
        """
        peers = []
        for vpnclient in self._get_peer_queryset():
            if vpnclient.ip:
                ip_address = ipaddress.ip_address(vpnclient.ip.ip_address)
                peers.append(
                    {
                        'public_key': vpnclient.public_key,
                        'allowed_ips': f'{ip_address}/{ip_address.max_prefixlen}',
                    }
                )
        return peers

    def _add_vxlan(self, config):
        """
        Adds VXLAN peers to the generated configuration
        without the need of manual intervention.
        Modifies the config data structure as a side effect.
        """
        peers = self._get_vxlan_peers()
        # add peer list to conifg as a JSON file
        config.setdefault('files', [])
        config['files'].append(
            {
                'mode': '0644',
                'path': 'vxlan.json',
                'contents': json.dumps(peers, indent=4, sort_keys=True),
            }
        )

    @cache_memoize(_PEER_CACHE_TIMEOUT, args_rewrite=_peer_cache_key)
    def _get_vxlan_peers(self):
        """
        Returns list of vxlan peers, the result is cached.
        """
        peers = []
        for vpnclient in self._get_peer_queryset():
            if vpnclient.ip:
                peers.append({'vni': vpnclient.vni, 'remote': vpnclient.ip.ip_address})
        return peers


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
    # optional, needed for VPNs which require setting a specific known IP (wireguard)
    ip = models.ForeignKey(
        get_model_name('openwisp_ipam', 'IpAddress'),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    # needed for wireguard
    public_key = models.CharField(blank=True, max_length=44)
    private_key = models.CharField(blank=True, max_length=44)
    # needed for vxlan
    vni = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(16777216)],
        db_index=True,
    )
    _auto_ip_stopper_funcs = []

    class Meta:
        abstract = True
        unique_together = (
            ('config', 'vpn'),
            ('vpn', 'vni'),
        )
        verbose_name = _('VPN client')
        verbose_name_plural = _('VPN clients')

    @classmethod
    def register_auto_ip_stopper(cls, func):
        """
        Adds "func" to "_auto_ip_stopper_funcs".
        These functions are called in the "_auto_ip" method.
        Output from these functions are used to determine
        skipping automatic IP assignment.
        """
        if func not in cls._auto_ip_stopper_funcs:
            cls._auto_ip_stopper_funcs.append(func)

    def save(self, *args, **kwargs):
        """
        automatically provisions tunnel keys
        and configuration if ``auto_cert`` is True
        """
        if self.auto_cert:
            self._auto_x509()
            self._auto_ip()
            self._auto_wireguard()
            self._auto_vxlan()
        super().save(*args, **kwargs)

    def _auto_x509(self):
        """
        automatically creates an x509 certificate
        """
        if not self.vpn._is_backend_type('openvpn') or self.cert:
            return
        cn = self._get_common_name()
        self._auto_create_cert(name=self.config.device.name, common_name=cn)

    def _get_common_name(self):
        """
        returns the common name for a new certificate
        """
        d = self.config.device
        end = 63 - len(d.mac_address)
        d.name = d.name[:end]
        unique_slug = shortuuid.ShortUUID().random(length=8)
        cn_format = app_settings.COMMON_NAME_FORMAT
        if cn_format == '{mac_address}-{name}' and d.name == d.mac_address:
            cn_format = '{mac_address}'
        common_name = cn_format.format(**d.__dict__)[:55]
        common_name = f'{common_name}-{unique_slug}'
        return common_name

    @classmethod
    def post_save(cls, instance, **kwargs):
        def _post_save():
            instance.vpn._invalidate_peer_cache(update=True)

        transaction.on_commit(_post_save)

    @classmethod
    def post_delete(cls, instance, **kwargs):
        """
        class method for ``post_delete`` signal
        automatically deletes related certificates
        and ip addresses if necessary
        """
        # only invalidates, does not regenerate the cache
        # to avoid generating high load during bulk deletes
        instance.vpn._invalidate_peer_cache()
        try:
            if instance.cert:
                instance.cert.delete()
        except ObjectDoesNotExist:
            pass
        try:
            if instance.ip:
                instance.ip.delete()
        except ObjectDoesNotExist:
            pass

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

    def _auto_wireguard(self):
        """
        Automatically generates private and public key for wireguard
        """
        if not self.vpn._is_backend_type('wireguard') or (
            self.private_key and self.public_key
        ):
            return
        self.private_key, self.public_key = crypto.generate_wireguard_keys()

    def _auto_vxlan(self):
        """
        Automatically generates VNI for VXLAN
        """
        if not self.vpn._is_backend_type('vxlan') or self.vni:
            return
        last_tunnel = (
            self._meta.model.objects.filter(vpn=self.vpn).order_by('vni').last()
        )
        if last_tunnel:
            self.vni = last_tunnel.vni + 1
        else:
            self.vni = 1

    def _auto_ip(self):
        if not self.vpn.subnet:
            return
        for func in self._auto_ip_stopper_funcs:
            if func(self):
                return
        self.ip = self.vpn.subnet.request_ip()

    @classmethod
    def invalidate_clients_cache(cls, vpn):
        """
        Invalidate checksum cache for clients that uses this VPN server
        """
        for client in vpn.vpnclient_set.iterator():
            # invalidate cache for device
            client.config._send_config_modified_signal(
                action='related_template_changed'
            )

import collections
import ipaddress
import logging

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.utils.translation import ugettext_lazy as _
from django_netjsonconfig.base.base import BaseModel
from jsonfield import JSONField
from jsonschema.exceptions import ValidationError as SchemaError

from openwisp_users.mixins import ShareableOrgMixin
from openwisp_utils.base import TimeStampedEditableModel

from . import settings as app_settings
from .utils import get_interfaces

logger = logging.getLogger(__name__)


class ConnectorMixin(object):
    _connector_field = 'connector'

    def clean(self):
        self._validate_connector_schema()

    def _validate_connector_schema(self):
        try:
            self.connector_class.validate(self.get_params())
        except SchemaError as e:
            raise ValidationError({'params': e.message})

    def get_params(self):
        return self.params

    def get_addresses(self):
        return []

    @cached_property
    def connector_class(self):
        return import_string(getattr(self, self._connector_field))

    @cached_property
    def connector_instance(self):
        return self.connector_class(params=self.get_params(),
                                    addresses=self.get_addresses())


class Credentials(ConnectorMixin, ShareableOrgMixin, BaseModel):
    """
    Credentials for access
    """
    connector = models.CharField(_('connection type'),
                                 choices=app_settings.CONNECTORS,
                                 max_length=128,
                                 db_index=True)
    params = JSONField(_('parameters'),
                       default=dict,
                       help_text=_('global connection parameters'),
                       load_kwargs={'object_pairs_hook': collections.OrderedDict},
                       dump_kwargs={'indent': 4})

    class Meta:
        verbose_name = _('Access credentials')
        verbose_name_plural = verbose_name

    def __str__(self):
        return '{0} ({1})'.format(self.name, self.get_connector_display())


class DeviceConnection(ConnectorMixin, TimeStampedEditableModel):
    _connector_field = 'update_strategy'
    device = models.ForeignKey('config.Device', on_delete=models.CASCADE)
    credentials = models.ForeignKey(Credentials, on_delete=models.CASCADE)
    update_strategy = models.CharField(_('update strategy'),
                                       help_text=_('leave blank to determine automatically'),
                                       choices=app_settings.UPDATE_STRATEGIES,
                                       max_length=128,
                                       blank=True,
                                       db_index=True)
    enabled = models.BooleanField(default=True, db_index=True)
    params = JSONField(_('parameters'),
                       default=dict,
                       blank=True,
                       help_text=_('local connection parameters (will override '
                                   'the global parameters if specified)'),
                       load_kwargs={'object_pairs_hook': collections.OrderedDict},
                       dump_kwargs={'indent': 4})
    # usability improvements
    is_working = models.NullBooleanField(default=None)
    failure_reason = models.CharField(_('reason of failure'),
                                      max_length=128,
                                      blank=True)
    last_attempt = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = _('Device connection')
        verbose_name_plural = _('Device connections')

    def clean(self):
        cred_org = self.credentials.organization
        if cred_org and cred_org != self.device.organization:
            raise ValidationError({
                'credentials': _('The organization of these credentials doesn\'t '
                                 'match the organization of the device')
            })
        if not self.update_strategy and hasattr(self.device, 'config'):
            try:
                self.update_strategy = app_settings.CONFIG_UPDATE_MAPPING[self.device.config.backend]
            except KeyError as e:
                raise ValidationError({
                    'update_stragy': _('could not determine update strategy '
                                       ' automatically, exception: {0}'.format(e))
                })
        elif not self.update_strategy:
            raise ValidationError({
                'update_strategy': _('the update strategy can be determined automatically '
                                     'only if the device has a configuration specified, '
                                     'because it is inferred from the configuration backend. '
                                     'Please select the update strategy manually.')
            })
        self._validate_connector_schema()

    def get_addresses(self):
        """
        returns a list of ip addresses for the related device
        (used to pass a list of ip addresses to a DeviceConnection instance)
        """
        deviceip_set = list(self.device.deviceip_set.all()
                                       .only('address')
                                       .order_by('priority'))
        address_list = []
        for deviceip in deviceip_set:
            address = deviceip.address
            ip = ipaddress.ip_address(address)
            if not ip.is_link_local:
                address_list.append(address)
            else:
                for interface in get_interfaces():
                    address_list.append('{0}%{1}'.format(address, interface))
        if self.device.management_ip:
            address_list.append(self.device.management_ip)
        if self.device.last_ip:
            address_list.append(self.device.last_ip)
        return address_list

    def get_params(self):
        params = self.credentials.params.copy()
        params.update(self.params)
        return params

    def connect(self):
        try:
            self.connector_instance.connect()
        except Exception as e:
            self.is_working = False
            self.failure_reason = str(e)
        else:
            self.is_working = True
            self.failure_reason = ''
        finally:
            self.last_attempt = timezone.now()
            self.save()

    def disconnect(self):
        self.connector_instance.disconnect()

    def update_config(self):
        self.connect()
        if self.is_working:
            try:
                self.connector_instance.update_config()
            except Exception as e:
                logger.exception(e)
            else:
                self.device.config.set_status_running()
                self.disconnect()


@python_2_unicode_compatible
class DeviceIp(TimeStampedEditableModel):
    device = models.ForeignKey('config.Device', on_delete=models.CASCADE)
    address = models.GenericIPAddressField(_('IP address'))
    priority = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = _('Device IP')
        verbose_name_plural = _('Device IP addresses')

    def __str__(self):
        return self.address

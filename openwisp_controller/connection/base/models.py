import collections
import logging

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from jsonschema.exceptions import ValidationError as SchemaError
from swapper import get_model_name, load_model

from openwisp_controller.config.base.base import BaseModel
from openwisp_users.mixins import ShareableOrgMixin
from openwisp_utils.base import TimeStampedEditableModel

from .. import settings as app_settings
from ..signals import is_working_changed

logger = logging.getLogger(__name__)


class ConnectorMixin(object):
    _connector_field = 'connector'

    def clean(self):
        # Validate the connector field here to avoid ImportError in case that
        # it is not valid (eg. it is an empty string because the user has forgotten
        # to pick up one from the choices). The field value is validated in a later
        # stage anyways. We are returning {} to avoid showing a duplicate error
        # message for the field
        if not self._get_connector():
            raise ValidationError({})
        self._validate_connector_schema()

    def _get_connector(self):
        return getattr(self, self._connector_field)

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
        connector = self._get_connector()
        return import_string(connector)

    @cached_property
    def connector_instance(self):
        return self.connector_class(
            params=self.get_params(), addresses=self.get_addresses()
        )


class AbstractCredentials(ConnectorMixin, ShareableOrgMixin, BaseModel):
    """
    Credentials for access
    """

    connector = models.CharField(
        _('connection type'),
        choices=app_settings.CONNECTORS,
        max_length=128,
        db_index=True,
    )
    params = JSONField(
        _('parameters'),
        default=dict,
        help_text=_('global connection parameters'),
        load_kwargs={'object_pairs_hook': collections.OrderedDict},
        dump_kwargs={'indent': 4},
    )
    auto_add = models.BooleanField(
        _('auto add'),
        default=False,
        help_text=_(
            'automatically add these credentials '
            'to the devices of this organization; '
            'if no organization is specified will '
            'be added to all the new devices'
        ),
    )

    class Meta:
        verbose_name = _('Access credentials')
        verbose_name_plural = verbose_name
        abstract = True

    def __str__(self):
        return '{0} ({1})'.format(self.name, self.get_connector_display())

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.auto_add_to_devices()

    def auto_add_to_devices(self):
        """
        When ``auto_add`` is ``True``, adds the credentials
        to each relevant ``Device`` and ``DeviceConnection`` objects
        """
        if not self.auto_add:
            return
        device_model = load_model('config', 'Device')
        devices = device_model.objects.exclude(config=None)
        org = self.organization
        if org:
            devices = devices.filter(organization=org)
        # exclude devices which have been already added
        devices = devices.exclude(deviceconnection__credentials=self)
        for device in devices:
            DeviceConnection = load_model('connection', 'DeviceConnection')
            conn = DeviceConnection(device=device, credentials=self, enabled=True)
            conn.full_clean()
            conn.save()

    @classmethod
    def auto_add_credentials_to_device(cls, instance, created, **kwargs):
        """
        Adds relevant credentials as ``DeviceConnection``
        when a device is created, this is called from a
        post_save signal receiver hooked to the ``Config`` model
        (why ``Config`` and not ``Device``? because at the moment
         we can automatically create a DeviceConnection if we have
         a ``Config`` object)
        """
        if not created:
            return
        device = instance.device
        # select credentials which
        #   - are flagged as auto_add
        #   - belong to the same organization of the device
        #     OR
        #     belong to no organization (hence are shared)
        conditions = models.Q(organization=device.organization) | models.Q(
            organization=None
        )
        credentials = cls.objects.filter(conditions).filter(auto_add=True)
        for cred in credentials:
            DeviceConnection = load_model('connection', 'DeviceConnection')
            conn = DeviceConnection(device=device, credentials=cred, enabled=True)
            conn.full_clean()
            conn.save()


class AbstractDeviceConnection(ConnectorMixin, TimeStampedEditableModel):
    _connector_field = 'update_strategy'
    device = models.ForeignKey(
        get_model_name('config', 'Device'), on_delete=models.CASCADE
    )
    credentials = models.ForeignKey(
        get_model_name('connection', 'Credentials'), on_delete=models.CASCADE
    )
    update_strategy = models.CharField(
        _('update strategy'),
        help_text=_('leave blank to determine automatically'),
        choices=app_settings.UPDATE_STRATEGIES,
        max_length=128,
        blank=True,
        db_index=True,
    )
    enabled = models.BooleanField(default=True, db_index=True)
    params = JSONField(
        _('parameters'),
        default=dict,
        blank=True,
        help_text=_(
            'local connection parameters (will override '
            'the global parameters if specified)'
        ),
        load_kwargs={'object_pairs_hook': collections.OrderedDict},
        dump_kwargs={'indent': 4},
    )
    # usability improvements
    is_working = models.BooleanField(null=True, blank=True, default=None)
    failure_reason = models.TextField(_('reason of failure'), blank=True)
    last_attempt = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = _('Device connection')
        verbose_name_plural = _('Device connections')
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_is_working = self.is_working

    def clean(self):
        cred_org = self.credentials.organization
        if cred_org and cred_org != self.device.organization:
            raise ValidationError(
                {
                    'credentials': _(
                        'The organization of these credentials doesn\'t '
                        'match the organization of the device'
                    )
                }
            )
        if not self.update_strategy and self.device._has_config():
            try:
                self.update_strategy = app_settings.CONFIG_UPDATE_MAPPING[
                    self.device.config.backend
                ]
            except KeyError as e:
                raise ValidationError(
                    {
                        'update_stragy': _(
                            'could not determine update strategy '
                            ' automatically, exception: {0}'.format(e)
                        )
                    }
                )
        elif not self.update_strategy:
            raise ValidationError(
                {
                    'update_strategy': _(
                        'the update strategy can be determined automatically '
                        'only if the device has a configuration specified, '
                        'because it is inferred from the configuration backend. '
                        'Please select the update strategy manually.'
                    )
                }
            )
        self._validate_connector_schema()

    def get_addresses(self):
        """
        returns a list of ip addresses that can be used to connect to the device
        (used to pass a list of ip addresses to a DeviceConnection instance)
        """
        address_list = []
        if self.device.management_ip:
            address_list.append(self.device.management_ip)
        if self.device.last_ip and self.device.last_ip != self.device.management_ip:
            address_list.append(self.device.last_ip)
        return address_list

    def get_params(self):
        params = self.credentials.params.copy()
        params.update(self.params)
        return params

    def set_connector(self, connector):
        self.connector_instance = connector

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
        return self.is_working

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
                self.device.config.set_status_applied()
                self.disconnect()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_working != self._initial_is_working:
            self.send_is_working_changed_signal()
        self._initial_is_working = self.is_working

    def send_is_working_changed_signal(self):
        is_working_changed.send(
            sender=self.__class__,
            is_working=self.is_working,
            old_is_working=self._initial_is_working,
            failure_reason=self.failure_reason,
            instance=self,
        )

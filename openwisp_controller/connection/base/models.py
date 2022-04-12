import collections
import logging

import jsonschema
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField
from jsonschema.exceptions import ValidationError as SchemaError
from swapper import get_model_name, load_model

from openwisp_controller.config.base.base import BaseModel
from openwisp_utils.base import TimeStampedEditableModel

from ...base import ShareableOrgMixinUniqueName
from .. import settings as app_settings
from ..commands import (
    COMMAND_CHOICES,
    DEFAULT_COMMANDS,
    get_command_callable,
    get_command_schema,
)
from ..signals import is_working_changed
from ..tasks import auto_add_credentials_to_devices, launch_command

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


class AbstractCredentials(ConnectorMixin, ShareableOrgMixinUniqueName, BaseModel):
    """
    Credentials for access
    """

    # Controls the number of objects which can be stored in memory
    # before commiting them to database during bulk auto add operation.
    chunk_size = 1000

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
        unique_together = ('name', 'organization')
        abstract = True

    def __str__(self):
        return '{0} ({1})'.format(self.name, self.get_connector_display())

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.auto_add:
            transaction.on_commit(
                lambda: auto_add_credentials_to_devices.delay(
                    credential_id=self.pk, organization_id=self.organization_id
                )
            )

    @classmethod
    def auto_add_to_devices(cls, credential_id, organization_id):
        """
        When ``auto_add`` is ``True``, adds the credentials
        to each relevant ``Device`` and ``DeviceConnection`` objects
        """
        DeviceConnection = load_model('connection', 'DeviceConnection')
        Device = load_model('config', 'Device')

        devices = Device.objects.exclude(config=None)
        if organization_id:
            devices = devices.filter(organization_id=organization_id)
        # exclude devices which have been already added
        devices = devices.exclude(deviceconnection__credentials_id=credential_id)
        device_connections = []
        for device in devices.iterator():
            conn = DeviceConnection(
                device=device, credentials_id=credential_id, enabled=True
            )
            conn.full_clean()
            device_connections.append(conn)
            # Send create query when chunk_size is reached
            # and reset the device_connections list
            if len(device_connections) >= cls.chunk_size:
                DeviceConnection.objects.bulk_create(device_connections)
                device_connections = []
        if len(device_connections):
            DeviceConnection.objects.bulk_create(device_connections)

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
        from django.contrib.contenttypes.models import ContentType
        from reversion.models import Version

        DeviceConnection = load_model('connection', 'DeviceConnection')

        if not created:
            return
        device = instance.device
        # select credentials which
        #   - are flagged as auto_add
        #   - belong to the same organization of the device
        #     OR
        #     belong to no organization (hence are shared)
        where = models.Q(auto_add=True) & (
            models.Q(organization=device.organization) | models.Q(organization=None)
        )
        # Exclude credentials for which DeviceConnection object already
        # exists for the device. This condition is required when a
        # deleted device is recovered through django-reversions.
        not_where = models.Q(
            id__in=device.deviceconnection_set.values_list('credentials_id', flat=True)
        )
        # A race condition might occur while recovering a deleted device.
        # The code for creating new DeviceConnection might be executed
        # before the deleted DeviceConnection object is restored from the database.
        # Therefore, when creating DeviceConnection objects in this method,
        # we make sure to avoid creating objects for credentials which are
        # stored in the revision history of django-reversion so that when a
        # deleted device is restored from the revision history we avoid
        # this race condition which would generate two identical DeviceConnection
        # objects and hence prevent the restoration of a deleted device.
        device_connection_versions = Version.objects.filter(
            content_type=ContentType.objects.get_for_model(DeviceConnection),
            serialized_data__contains=str(device.id),
        )
        versioned_credentials = []
        for version in device_connection_versions:
            versioned_credentials.append(version.field_dict['credentials_id'])
        not_where |= models.Q(id__in=versioned_credentials)
        credentials = cls.objects.filter(where).exclude(not_where)
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
        self._initial_failure_reason = self.failure_reason

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
        self._initial_failure_reason = self.failure_reason

    def send_is_working_changed_signal(self):
        is_working_changed.send(
            sender=self.__class__,
            is_working=self.is_working,
            old_is_working=self._initial_is_working,
            failure_reason=self.failure_reason,
            old_failure_reason=self._initial_failure_reason,
            instance=self,
        )


class AbstractCommand(TimeStampedEditableModel):
    STATUS_CHOICES = (
        ('in-progress', _('in progress')),
        ('success', _('success')),
        ('failed', _('failed')),
    )
    device = models.ForeignKey(
        get_model_name('config', 'Device'), on_delete=models.CASCADE
    )
    # if the related DeviceConnection is deleted,
    # set this to NULL to avoid losing history
    connection = models.ForeignKey(
        get_model_name('connection', 'DeviceConnection'),
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0]
    )
    type = models.CharField(max_length=16, choices=COMMAND_CHOICES)
    input = JSONField(
        blank=True,
        null=True,
        load_kwargs={'object_pairs_hook': collections.OrderedDict},
        dump_kwargs={'indent': 4},
    )
    output = models.TextField(blank=True)

    class Meta:
        verbose_name = _('Command')
        verbose_name_plural = _('Commands')
        abstract = True
        ordering = ('created',)

    def __str__(self):
        command = self.input['command'] if self.is_custom else self.get_type_display()
        limit = 32
        if len(command) > limit:
            command = f'{command[:limit]}…'
        sent = _('sent on')
        created = timezone.localtime(self.created)
        return f'«{command}» {sent} {created.strftime("%d %b %Y at %I:%M %p")}'

    def full_clean(self, *args, **kwargs):
        """
        Automatically sets the connection field if empty
        Will be done before the rest of the validation process
        to avoid triggering validation errors.
        """
        if not self.connection:
            self.connection = self.device.deviceconnection_set.first()
        return super().full_clean(*args, **kwargs)

    def clean(self):
        try:
            jsonschema.Draft4Validator(self._schema).validate(self.input)
        except SchemaError as e:
            raise ValidationError({'input': e.message})

    @property
    def is_custom(self):
        return self.type == 'custom'

    @property
    def is_default_command(self):
        return self.type in DEFAULT_COMMANDS.keys()

    def save(self, *args, **kwargs):
        """
        Automatically schedules execution of
        commands in the background upon creation.
        """
        adding = self._state.adding
        if adding:
            self.full_clean()
        output = super().save(*args, **kwargs)
        if adding:
            self._schedule_command()
        return output

    def _schedule_command(self):
        """
        executes ``launch_command`` celery taks in the background
        once changes are committed to the database
        """
        transaction.on_commit(lambda: launch_command.delay(self.pk))

    def execute(self):
        """
        Launches the execution of commands and based
        on the connection status or exit codes
        it determines if the commands succeeded or not
        """
        if self.status in ['failed', 'success']:
            raise RuntimeError(
                'This command has already been executed, ' 'please create a new one.'
            )
        exit_code = self._exec_command()
        # if output is None, the commands couldn't execute
        # because the system couldn't connect to the device
        if exit_code is None:
            self.status = 'failed'
            self.output = self.connection.failure_reason
        # one command failed
        elif exit_code != 0:
            self.status = 'failed'
        # all commands succeeded
        else:
            self.status = 'success'
        self._clean_sensitive_info()
        self.save()

    def _exec_command(self):
        """
        Executes commands, stores output, returns exit_code
        """
        self.connection.connect()
        # if couldn't connect to device, stop here
        if not self.connection.is_working:
            return None
        # custom commands, perform each one separately and save output incrementally
        if self.is_custom:
            command = self.custom_command
            output, exit_code = self.connection.connector_instance.exec_command(
                command, raise_unexpected_exit=False
            )
        # default commands
        elif self.is_default_command:
            output, exit_code = self._execute_predefined_command()
            command = self.get_type_display()
        # user registered command
        else:
            command = self._callable(**self.input)
            output, exit_code = self.connection.connector_instance.exec_command(
                command, raise_unexpected_exit=False
            )
        self._add_output(output)
        # if got non zero exit code, add extra info
        if exit_code != 0:
            self._add_output(
                gettext(f'Command "{command}" returned non-zero exit code: {exit_code}')
            )
        # loop completed (or broken), disconnect
        self.connection.disconnect()
        return exit_code

    def _execute_predefined_command(self):
        method = getattr(self.connection.connector_instance, self.type)
        return method(*self.arguments)

    def _add_output(self, output):
        """
        adds trailing new line if output doesn't have it
        """
        output = str(output)  # convert __proxy__ strings
        if not output.endswith('\n'):
            output += '\n'
        self.output += output

    def _clean_sensitive_info(self):
        """
        Removes sensitive information from input field if necessary
        """
        if self.type == 'change_password':
            self.input = {'password': '********'}

    @property
    def custom_command(self):
        if not self.is_custom:
            raise TypeError(
                f'custom_commands property is not applicable in '
                f'command instance of type "{self.type}"'
            )
        return self.input['command']

    @property
    def arguments(self):
        """
        Interprets input as comma separated arguments
        """
        self._enforce_not_custom()
        if self.input:
            return self.input.values()
        return []

    @property
    def input_data(self):
        if self.is_custom:
            return self.custom_command
        else:
            return ', '.join(self.arguments)

    @property
    def _schema(self):
        return get_command_schema(self.type)

    @property
    def _callable(self):
        """
        Returns callable of user registered command
        """
        method = get_command_callable(self.type)
        if callable(method):
            return method
        return import_string(method)

    def _enforce_not_custom(self):
        if self.is_custom:
            raise TypeError(
                f'arguments property is not applicable in '
                f'command instance of type "{self.type}"'
            )

from hashlib import md5

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name, load_model

from openwisp_users.mixins import OrgMixin
from openwisp_utils.base import KeyField

from .. import settings as app_settings
from ..signals import (
    device_activated,
    device_deactivated,
    device_group_changed,
    device_name_changed,
    management_ip_changed,
)
from ..validators import device_name_validator, mac_address_validator
from .base import BaseModel


class AbstractDevice(OrgMixin, BaseModel):
    """
    Base device model
    Stores information related to the
    physical properties of a network device
    """

    _changed_checked_fields = ['name', 'group_id', 'management_ip', 'organization_id']

    name = models.CharField(
        max_length=64,
        unique=False,
        validators=[device_name_validator],
        db_index=True,
        help_text=_('must be either a valid hostname or mac address'),
    )
    mac_address = models.CharField(
        max_length=17,
        db_index=True,
        unique=False,
        validators=[mac_address_validator],
        help_text=_('primary mac address'),
    )
    key = KeyField(
        unique=True,
        blank=True,
        default=None,
        db_index=True,
        help_text=_('unique device key'),
    )
    model = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text=_('device model and manufacturer'),
    )
    os = models.CharField(
        _('operating system'),
        blank=True,
        db_index=True,
        max_length=128,
        help_text=_('operating system identifier'),
    )
    system = models.CharField(
        _('SOC / CPU'),
        blank=True,
        db_index=True,
        max_length=128,
        help_text=_('system on chip or CPU info'),
    )
    notes = models.TextField(blank=True, help_text=_('internal notes'))
    group = models.ForeignKey(
        get_model_name('config', 'DeviceGroup'),
        verbose_name=_('group'),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    # these fields are filled automatically
    # with data received from devices
    last_ip = models.GenericIPAddressField(
        blank=True,
        null=True,
        db_index=True,
        help_text=_(
            'indicates the IP address logged from '
            'the last request coming from the device'
        ),
    )
    management_ip = models.GenericIPAddressField(
        blank=True,
        null=True,
        db_index=True,
        help_text=_(
            'IP address used by the system to reach the device when performing '
            'any type of push operation or active check. The value of this field is '
            'generally sent by the device and hence does not need to be changed, '
            'but can be changed or cleared manually if needed.'
        ),
    )
    hardware_id = models.CharField(**(app_settings.HARDWARE_ID_OPTIONS))
    # This is an internal field which is used to track if
    # the device has been deactivated. This field should not be changed
    # directly, use the deactivate() method instead.
    _is_deactivated = models.BooleanField(default=False)

    class Meta:
        unique_together = (
            ('mac_address', 'organization'),
            ('hardware_id', 'organization'),
        )
        abstract = True
        verbose_name = app_settings.DEVICE_VERBOSE_NAME[0]
        verbose_name_plural = app_settings.DEVICE_VERBOSE_NAME[1]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_initial_values_for_changed_checked_fields()

    def _set_initial_values_for_changed_checked_fields(self):
        for field in self._changed_checked_fields:
            if self._is_deferred(field):
                setattr(self, f'_initial_{field}', models.DEFERRED)
            else:
                setattr(self, f'_initial_{field}', getattr(self, field))

    def __str__(self):
        return (
            self.hardware_id
            if (app_settings.HARDWARE_ID_ENABLED and app_settings.HARDWARE_ID_AS_NAME)
            else self.name
        )

    def _has_config(self):
        return hasattr(self, 'config')

    def _has_group(self):
        return hasattr(self, 'group') and self.group is not None

    def _has_organization__config_settings(self):
        return hasattr(self, 'organization') and hasattr(
            self.organization, 'config_settings'
        )

    def _get_config_attr(self, attr):
        """
        gets property or calls method of related config object
        without rasing an exception if config is not set
        """
        if not self._has_config():
            return None
        attr = getattr(self.config, attr)
        return attr() if callable(attr) else attr

    def _get_config(self):
        if self._has_config():
            return self.config
        else:
            return self.get_config_model()(device=self)

    def _get_group(self):
        if self._has_group():
            return self.group
        return self.get_group_model()(device=self)

    def _get_organization__config_settings(self):
        if self._has_organization__config_settings():
            return self.organization.config_settings
        return load_model('config', 'OrganizationConfigSettings')(
            organization=self.organization if hasattr(self, 'organization') else None
        )

    def is_deactivated(self):
        return self._is_deactivated

    def deactivate(self):
        if self.is_deactivated():
            # The device has already been deactivated.
            # No further operation is required.
            return
        with transaction.atomic():
            if self._has_config():
                self.config.deactivate()
            else:
                self.management_ip = ''
            self._is_deactivated = True
            self.save()
            device_deactivated.send(sender=self.__class__, instance=self)

    def activate(self):
        if not self.is_deactivated():
            # The device is already active.
            # No further operation is required.
            return
        with transaction.atomic():
            if self._has_config():
                self.config.activate()
            self._is_deactivated = False
            self.save()
            device_activated.send(sender=self.__class__, instance=self)

    def get_context(self):
        config = self._get_config()
        return config.get_context()

    def get_system_context(self):
        config = self._get_config()
        return config.get_system_context()

    def generate_key(self, shared_secret):
        if app_settings.CONSISTENT_REGISTRATION:
            keybase = (
                self.hardware_id
                if app_settings.HARDWARE_ID_ENABLED
                else self.mac_address
            )
            hash_key = md5('{}+{}'.format(keybase, shared_secret).encode('utf-8'))
            return hash_key.hexdigest()
        else:
            return KeyField.default_callable()

    def _validate_org_device_limit(self):
        if not self._state.adding and not self._check_organization_id_changed():
            # This check is only executed when a new device
            # is created.
            return
        if (
            not hasattr(self, 'organization')
            or self.organization.config_limits.device_limit == 0
        ):
            return
        device_count = self._meta.model.objects.filter(
            organization=self.organization
        ).count()
        device_limit = self.organization.config_limits.device_limit
        if not device_limit or device_count >= device_limit:
            raise ValidationError(
                _(
                    (
                        'The maximum amount of allowed devices has been reached'
                        ' for organization {org}.'
                    ).format(org=self.organization.name)
                )
            )

    def _validate_unique_name(self):
        if app_settings.DEVICE_NAME_UNIQUE:
            if (
                hasattr(self, 'organization')
                and self._meta.model.objects.filter(
                    ~Q(id=self.id),
                    organization=self.organization,
                    name__iexact=self.name,
                ).exists()
            ):
                raise ValidationError(
                    _('Device with this Name and Organization already exists.')
                )

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        self.mac_address = self.mac_address.upper()
        self._validate_unique_name()
        self._validate_org_relation('group', field_error='group')
        self._validate_org_device_limit()

    def save(self, *args, **kwargs):
        if not self.key:
            try:
                shared_secret = self.organization.config_settings.shared_secret
            except ObjectDoesNotExist:
                # should not happen, but if organization config settings
                # is not defined the default key will default to being random
                self.key = KeyField.default_callable()
            else:
                self.key = self.generate_key(shared_secret)
        state_adding = self._state.adding
        super().save(*args, **kwargs)
        if state_adding and self.group and self.group.templates.exists():
            self.create_default_config()
        # The value of "self._state.adding" will always be "False"
        # after performing the save operation. Hence, the actual value
        # is stored in the "state_adding" variable.
        if not state_adding:
            self._check_changed_fields()

    def delete(self, using=None, keep_parents=False, check_deactivated=True):
        if check_deactivated and (
            not self.is_deactivated()
            or (self._has_config() and not self.config.is_deactivated())
        ):
            raise PermissionDenied('The device must be deactivated prior to deletion')
        return super().delete(using, keep_parents)

    def _check_changed_fields(self):
        self._get_initial_values_for_checked_fields()
        # Execute method for checked for each field in self._changed_checked_fields
        for field in self._changed_checked_fields:
            getattr(self, f'_check_{field}_changed')()

    def _is_deferred(self, field):
        """
        Return a boolean whether the field is deferred.
        """
        return field in self.get_deferred_fields()

    def _get_initial_values_for_checked_fields(self):
        # Refresh values from database only when the checked field
        # was initially deferred, but is no longer deferred now.
        # Store the present value of such fields because they will
        # be overwritten fetching values from database
        # NOTE: Initial value of a field will only remain deferred
        # if the current value of the field is still deferred. This
        present_values = dict()
        for field in self._changed_checked_fields:
            if getattr(
                self, f'_initial_{field}'
            ) == models.DEFERRED and not self._is_deferred(field):
                present_values[field] = getattr(self, field)
        # Skip fetching values from database if all of the checked fields are
        # still deferred, or were not deferred from the begining.
        if not present_values:
            return
        self.refresh_from_db(fields=present_values.keys())
        for field in self._changed_checked_fields:
            setattr(self, f'_initial_{field}', field)
            setattr(self, field, present_values[field])

    def _check_name_changed(self):
        if self._initial_name == models.DEFERRED:
            return

        if self._initial_name != self.name:
            device_name_changed.send(
                sender=self.__class__,
                instance=self,
            )

            if self._has_config():
                self.config.set_status_modified()

    def _check_group_id_changed(self):
        if self._initial_group_id == models.DEFERRED:
            return

        if self._initial_group_id != self.group_id:
            self._send_device_group_changed_signal(
                self, self.group_id, self._initial_group_id
            )

    def _check_management_ip_changed(self):
        if self._initial_management_ip == models.DEFERRED:
            return
        if self.management_ip != self._initial_management_ip:
            management_ip_changed.send(
                sender=self.__class__,
                management_ip=self.management_ip,
                old_management_ip=self._initial_management_ip,
                instance=self,
            )

        self._initial_management_ip = self.management_ip

    def _check_organization_id_changed(self):
        """
        Returns "True" if the device's organization has changed.
        """
        return (
            self._initial_organization_id != models.DEFERRED
            and self.organization_id != self._initial_organization_id
        )

    @classmethod
    def _send_device_group_changed_signal(cls, instance, group_id, old_group_id):
        """
        Emits ``device_group_changed`` signal.
        Called also by ``change_device_group`` admin action method.
        """
        device_group_changed.send(
            sender=cls,
            instance=instance,
            group_id=group_id,
            old_group_id=old_group_id,
        )

    @property
    def backend(self):
        """
        Used as a shortcut for display purposes
        (eg: admin site)
        """
        return self._get_config_attr('get_backend_display')

    @property
    def status(self):
        """
        Used as a shortcut for display purposes
        (eg: admin site)
        """
        return self._get_config_attr('get_status_display')

    def get_default_templates(self):
        """
        calls `get_default_templates` of related
        config object (or new config instance)
        """
        if self._has_config():
            config = self.config
        else:
            config = self.get_temp_config_instance()
        return config.get_default_templates()

    @classmethod
    def get_config_model(cls):
        return cls._meta.get_field('config').related_model

    @classmethod
    def get_group_model(cls):
        return cls._meta.get_field('group').related_model

    @classmethod
    def get_config_settings_model(cls):
        return

    def get_temp_config_instance(self, **options):
        if not self._has_config():
            config = self.get_config_model()(**options)
        else:
            config = self.config
            for attr in options:
                setattr(config, attr, options[attr])
        config.device = self
        return config

    def can_be_updated(self):
        """
        returns True if the device can and should be updated
        can be overridden with custom logic if needed
        """
        return self.config.status != 'applied'

    def create_default_config(self, **options):
        """
        creates a new config instance to apply group templates
        if group has templates.
        """
        if not (self.group and self.group.templates.exists()):
            return
        config = self.get_temp_config_instance(
            backend=app_settings.DEFAULT_BACKEND, **options
        )
        config.save()

    @classmethod
    def manage_devices_group_templates(cls, device_ids, old_group_ids, group_id):
        """
        This method is used to manage group templates for devices.
        """
        Device = load_model('config', 'Device')
        DeviceGroup = load_model('config', 'DeviceGroup')
        Template = load_model('config', 'Template')
        if type(device_ids) is not list:
            device_ids = [device_ids]
            old_group_ids = [old_group_ids]
        for device_id, old_group_id in zip(device_ids, old_group_ids):
            device = Device.objects.get(pk=device_id)
            if not hasattr(device, 'config'):
                device.create_default_config()
            config_created = hasattr(device, 'config')
            if not config_created:
                # device has no config (device group has no templates)
                return
            group_templates = Template.objects.none()
            if group_id:
                group = DeviceGroup.objects.get(pk=group_id)
                group_templates = group.templates.all()
            old_group_templates = Template.objects.none()
            if old_group_id:
                old_group = DeviceGroup.objects.get(pk=old_group_id)
                old_group_templates = old_group.templates.all()
            device.config.manage_group_templates(group_templates, old_group_templates)

    @classmethod
    def config_deactivated_clear_management_ip(cls, instance, *args, **kwargs):
        """
        Clear management IP of the device when the device's config status
        is changed to 'deactivated'.
        """
        cls.objects.filter(pk=instance.device_id).update(management_ip='')

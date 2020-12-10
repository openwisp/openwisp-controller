from hashlib import md5

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.translation import ugettext_lazy as _

from openwisp_users.mixins import OrgMixin
from openwisp_utils.base import KeyField

from .. import settings as app_settings
from ..validators import device_name_validator, mac_address_validator
from .base import BaseModel


class AbstractDevice(OrgMixin, BaseModel):
    """
    Base device model
    Stores information related to the
    physical properties of a network device
    """

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
        help_text=_('ip address of the management interface, if available'),
    )
    hardware_id = models.CharField(**(app_settings.HARDWARE_ID_OPTIONS))

    class Meta:
        unique_together = (
            ('name', 'organization'),
            ('mac_address', 'organization'),
            ('hardware_id', 'organization'),
        )
        abstract = True
        verbose_name = app_settings.DEVICE_VERBOSE_NAME[0]
        verbose_name_plural = app_settings.DEVICE_VERBOSE_NAME[1]

    def __str__(self):
        return (
            self.hardware_id
            if (app_settings.HARDWARE_ID_ENABLED and app_settings.HARDWARE_ID_AS_NAME)
            else self.name
        )

    def clean(self):
        """
        modifies related config status if name
        attribute is changed (queries the database)
        """
        super().clean()
        if self._state.adding:
            return
        current = self.__class__.objects.get(pk=self.pk)
        if self.name != current.name and self._has_config():
            self.config.set_status_modified()

    def _has_config(self):
        return hasattr(self, 'config')

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
        super().save(*args, **kwargs)

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

    def get_temp_config_instance(self, **options):
        config = self.get_config_model()(**options)
        config.device = self
        return config

    def can_be_updated(self):
        """
        returns True if the device can and should be updated
        can be overridden with custom logic if needed
        """
        return self.config.status != 'applied'

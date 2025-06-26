import collections
from copy import deepcopy

import swapper
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField

from openwisp_utils.base import KeyField, UUIDModel
from openwisp_utils.fields import FallbackBooleanChoiceField

from .. import settings as app_settings
from ..exceptions import OrganizationDeviceLimitExceeded
from ..tasks import bulk_invalidate_config_get_cached_checksum


class AbstractOrganizationConfigSettings(UUIDModel):
    organization = models.OneToOneField(
        swapper.get_model_name("openwisp_users", "Organization"),
        verbose_name=_("organization"),
        related_name="config_settings",
        on_delete=models.CASCADE,
    )
    registration_enabled = models.BooleanField(
        _("auto-registration enabled"),
        default=True,
        help_text=_("Whether automatic registration of devices is enabled or not"),
    )
    shared_secret = KeyField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name=_("shared secret"),
        help_text=_("used for automatic registration of devices"),
    )
    whois_enabled = FallbackBooleanChoiceField(
        help_text=_("Whether the WHOIS lookup feature is enabled"),
        fallback=app_settings.WHOIS_ENABLED,
        verbose_name=_("WHOIS Enabled"),
    )
    context = JSONField(
        blank=True,
        default=dict,
        load_kwargs={"object_pairs_hook": collections.OrderedDict},
        dump_kwargs={"indent": 4},
        help_text=_(
            'This field can be used to add "Configuration Variables"' " to the devices."
        ),
        verbose_name=_("Configuration Variables"),
    )

    class Meta:
        verbose_name = _("Configuration management settings")
        verbose_name_plural = verbose_name
        abstract = True

    def __str__(self):
        return self.organization.name

    def get_context(self):
        return deepcopy(self.context)

    def clean(self):
        if not app_settings.WHOIS_CONFIGURED and self.whois_enabled:
            raise ValidationError(
                {
                    "whois_enabled": _(
                        "WHOIS_GEOIP_ACCOUNT and WHOIS_GEOIP_KEY must be set "
                        + "before enabling WHOIS feature."
                    )
                }
            )
        return super().clean()

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        context_changed = False
        if not self._state.adding:
            db_instance = self.__class__.objects.only("context").get(id=self.id)
            context_changed = db_instance.context != self.context
        super().save(force_insert, force_update, using, update_fields)
        if context_changed:
            bulk_invalidate_config_get_cached_checksum.delay(
                {"device__organization_id": str(self.organization_id)}
            )


class AbstractOrganizationLimits(models.Model):
    organization = models.OneToOneField(
        swapper.get_model_name("openwisp_users", "Organization"),
        verbose_name=_("organization"),
        primary_key=True,
        related_name="config_limits",
        on_delete=models.CASCADE,
    )
    device_limit = models.BigIntegerField(
        verbose_name=_("device limit"),
        default=0,
        null=True,
        blank=True,
        help_text=_(
            "Maximum number of devices allowed for this organization."
            ' "0" means unlimited.'
        ),
    )

    class Meta:
        verbose_name = _("controller limits")
        verbose_name_plural = verbose_name
        abstract = True

    def __str__(self):
        return self.organization.name

    def _validate_device_limit(self):
        """
        Checks if organization's device limit is greater
        than existing devices.
        """
        if self.device_limit == 0:
            return
        org_device_count = self.organization.device_set.count()
        if not self.device_limit or self.device_limit < org_device_count:
            raise OrganizationDeviceLimitExceeded()

    def clean(self):
        super().clean()
        if not self._state.adding:
            self._validate_device_limit()

    @classmethod
    def post_save_handler(cls, instance, created, *args, **kwargs):
        if not created:
            return
        org_allowed_devices = cls(organization=instance)
        org_allowed_devices.full_clean()
        org_allowed_devices.save()

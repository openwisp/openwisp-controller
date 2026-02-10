import collections
from copy import deepcopy

import swapper
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField

from openwisp_utils.base import KeyField, UUIDModel

from .. import tasks
from ..exceptions import OrganizationDeviceLimitExceeded


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "context" in self.get_deferred_fields():
            self._initial_context = models.DEFERRED
        else:
            self._initial_context = deepcopy(self.context)

    def __str__(self):
        return self.organization.name

    def get_context(self):
        return deepcopy(self.context)

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        context_changed = False
        context_in_update = update_fields is None or "context" in update_fields
        if not self._state.adding and context_in_update:
            initial_context = getattr(self, "_initial_context", None)
            if initial_context is not None and initial_context != models.DEFERRED:
                context_changed = initial_context != self.context
            elif initial_context == models.DEFERRED and context_in_update:
                # Conservative: if we don't know initial state and context is
                # being updated, assume it changed to avoid stale cache
                context_changed = True
        super().save(force_insert, force_update, using, update_fields)
        if context_changed and self.organization.is_active:
            organization_id = str(self.organization_id)
            transaction.on_commit(
                lambda: (
                    tasks.bulk_invalidate_config_get_cached_checksum.delay(
                        {"device__organization_id": organization_id}
                    ),
                    tasks.invalidate_organization_vpn_cache.delay(organization_id),
                ),
                using=using,
            )
        if context_in_update:
            if "context" in self.get_deferred_fields():
                self._initial_context = models.DEFERRED
            else:
                self._initial_context = deepcopy(self.context)


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

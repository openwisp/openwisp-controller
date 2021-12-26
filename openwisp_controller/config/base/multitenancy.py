import swapper
from django.db import models
from django.utils.translation import gettext_lazy as _

from openwisp_utils.base import KeyField, UUIDModel


class AbstractOrganizationConfigSettings(UUIDModel):

    organization = models.OneToOneField(
        swapper.get_model_name('openwisp_users', 'Organization'),
        verbose_name=_('organization'),
        related_name='config_settings',
        on_delete=models.CASCADE,
    )
    registration_enabled = models.BooleanField(
        _('auto-registration enabled'),
        default=True,
        help_text=_('Whether automatic registration of devices is enabled or not'),
    )
    shared_secret = KeyField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name=_('shared secret'),
        help_text=_('used for automatic registration of devices'),
    )

    class Meta:
        verbose_name = _('Configuration management settings')
        verbose_name_plural = verbose_name
        abstract = True

    def __str__(self):
        return self.organization.name

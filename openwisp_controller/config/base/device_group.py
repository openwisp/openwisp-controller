import collections

import jsonschema
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField
from jsonschema.exceptions import ValidationError as SchemaError

from openwisp_users.mixins import OrgMixin
from openwisp_utils.base import TimeStampedEditableModel

from .. import settings as app_settings


class AbstractDeviceGroup(OrgMixin, TimeStampedEditableModel):
    name = models.CharField(max_length=60, null=False, blank=False)
    description = models.TextField(blank=True, help_text=_('internal notes'))
    meta_data = JSONField(
        blank=True,
        default=dict,
        load_kwargs={'object_pairs_hook': collections.OrderedDict},
        dump_kwargs={'indent': 4},
    )

    def __str__(self):
        return self.name

    class Meta:
        abstract = True
        verbose_name = _('Device Group')
        verbose_name_plural = _('Device Groups')
        unique_together = (('organization', 'name'),)

    def clean(self):
        try:
            jsonschema.Draft4Validator(app_settings.DEVICE_GROUP_SCHEMA).validate(
                self.meta_data
            )
        except SchemaError as e:
            raise ValidationError({'input': e.message})

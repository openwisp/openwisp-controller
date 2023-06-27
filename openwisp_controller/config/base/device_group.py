import collections
from copy import deepcopy

import jsonschema
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField
from jsonschema.exceptions import ValidationError as SchemaError
from swapper import get_model_name, load_model

from openwisp_users.mixins import OrgMixin
from openwisp_utils.base import TimeStampedEditableModel

from .. import settings as app_settings
from ..signals import group_templates_changed
from ..sortedm2m.fields import SortedManyToManyField
from .config import TemplatesThrough


class AbstractDeviceGroup(OrgMixin, TimeStampedEditableModel):
    name = models.CharField(max_length=60, null=False, blank=False)
    description = models.TextField(blank=True, help_text=_('internal notes'))
    templates = SortedManyToManyField(
        get_model_name('config', 'Template'),
        related_name='device_group_relations',
        verbose_name=_('templates'),
        base_class=TemplatesThrough,
        blank=True,
        help_text=_(
            'These templates are automatically assigned to the devices '
            'that are part of the group. Default and required templates '
            'are excluded from this list. If the group of the device is '
            'changed, these templates will be automatically removed and '
            'the templates of the new group will be assigned.'
        ),
    )
    meta_data = JSONField(
        blank=True,
        default=dict,
        load_kwargs={'object_pairs_hook': collections.OrderedDict},
        dump_kwargs={'indent': 4},
        help_text=_(
            'Group meta data, use this field to store data which is related'
            ' to this group and can be retrieved via the REST API.'
        ),
        verbose_name=_('Metadata'),
    )
    context = JSONField(
        blank=True,
        default=dict,
        load_kwargs={'object_pairs_hook': collections.OrderedDict},
        dump_kwargs={'indent': 4},
        help_text=_(
            'This field can be used to add meta data for the group'
            ' or to add "Configuration Variables" to the devices.'
        ),
        verbose_name=_('Configuration Variables'),
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

    def get_context(self):
        return deepcopy(self.context)

    @classmethod
    def templates_changed(cls, instance, old_templates, templates, *args, **kwargs):
        group_templates_changed.send(
            sender=cls,
            instance=instance,
            templates=templates,
            old_templates=old_templates,
        )

    @classmethod
    def manage_group_templates(cls, group_id, old_template_ids, template_ids):
        """
        This method is used to change the templates of associated devices
        if group templates are changed.
        """
        DeviceGroup = load_model('config', 'DeviceGroup')
        Template = load_model('config', 'Template')
        device_group = DeviceGroup.objects.get(id=group_id)
        templates = Template.objects.filter(pk__in=template_ids)
        old_templates = Template.objects.filter(pk__in=old_template_ids)
        for device in device_group.device_set.iterator():
            if not hasattr(device, 'config'):
                device.create_default_config()
            device.config.manage_group_templates(templates, old_templates)

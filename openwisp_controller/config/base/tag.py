from django.db import models
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name
from taggit.models import GenericUUIDTaggedItemBase, TagBase, TaggedItemBase

from openwisp_utils.base import UUIDModel


class AbstractTemplateTag(TagBase, UUIDModel):
    class Meta:
        abstract = True
        verbose_name = _('Tag')
        verbose_name_plural = _('Tags')


class AbstractTaggedTemplate(GenericUUIDTaggedItemBase, TaggedItemBase):
    tag = models.ForeignKey(
        get_model_name('config', 'TemplateTag'),
        related_name='%(app_label)s_%(class)s_items',
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True
        verbose_name = _('Tagged item')
        verbose_name_plural = _('Tags')

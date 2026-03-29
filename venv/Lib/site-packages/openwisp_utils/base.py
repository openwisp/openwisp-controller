import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.fields import AutoCreatedField, AutoLastModifiedField

# For backward compatibility
from .fields import KeyField  # noqa


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedEditableModel(UUIDModel):
    """An abstract base class model that provides self-updating ``created`` and ``modified`` fields."""

    created = AutoCreatedField(_("created"), editable=True)
    modified = AutoLastModifiedField(_("modified"), editable=True)

    class Meta:
        abstract = True

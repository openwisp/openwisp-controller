from django.db import models
from django.utils.translation import gettext_lazy as _

from openwisp_utils.base import TimeStampedEditableModel


class Device(TimeStampedEditableModel):
    name = models.CharField(_("name"), max_length=75)

    def __str__(self):
        return self.name

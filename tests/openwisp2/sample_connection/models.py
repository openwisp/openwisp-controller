from django.db import models

from openwisp_controller.connection.base.models import (
    AbstractBatchCommand,
    AbstractCommand,
    AbstractCredentials,
    AbstractDeviceConnection,
)


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        abstract = True


class Credentials(DetailsModel, AbstractCredentials):
    class Meta(AbstractCredentials.Meta):
        abstract = False


class DeviceConnection(DetailsModel, AbstractDeviceConnection):
    class Meta(AbstractDeviceConnection.Meta):
        abstract = False


class Command(AbstractCommand):
    class Meta(AbstractCommand.Meta):
        abstract = False


class BatchCommand(AbstractBatchCommand):
    class Meta(AbstractBatchCommand.Meta):
        abstract = False

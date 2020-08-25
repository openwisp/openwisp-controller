import swapper

from .base.models import AbstractCommand, AbstractCredentials, AbstractDeviceConnection


class Credentials(AbstractCredentials):
    class Meta(AbstractCredentials.Meta):
        abstract = False
        swappable = swapper.swappable_setting('connection', 'Credentials')


class DeviceConnection(AbstractDeviceConnection):
    class Meta(AbstractDeviceConnection.Meta):
        abstract = False
        swappable = swapper.swappable_setting('connection', 'DeviceConnection')


class Command(AbstractCommand):
    class Meta(AbstractCommand.Meta):
        abstract = False
        swappable = swapper.swappable_setting('connection', 'Command')

import swapper

from .base.models import AbstractCredentials, AbstractDeviceConnection


class Credentials(AbstractCredentials):
    class Meta(AbstractCredentials.Meta):
        abstract = False
        swappable = swapper.swappable_setting('connection', 'Credentials')


class DeviceConnection(AbstractDeviceConnection):
    class Meta(AbstractDeviceConnection.Meta):
        swappable = swapper.swappable_setting('connection', 'DeviceConnection')

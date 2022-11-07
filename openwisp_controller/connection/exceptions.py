class NoWorkingDeviceConnectionError(Exception):
    """
    raised when none of the device's DeviceConnection
    are working.
    """

    def __init__(self, connection, *args: object):
        self.connection = connection
        super().__init__(*args)

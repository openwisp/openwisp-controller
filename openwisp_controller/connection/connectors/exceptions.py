class CommandFailedException(Exception):
    """
    raised when a command returns an unexpected result
    """

    pass


class CommandTimeoutException(Exception):
    """
    raised when a command times out
    """

    pass

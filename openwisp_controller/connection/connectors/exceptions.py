from openwisp_utils.tests import capture_any_output

@capture_any_output()
class CommandFailedException(Exception):


    """
    raised when a command returns an unexpected result
    """


    pass

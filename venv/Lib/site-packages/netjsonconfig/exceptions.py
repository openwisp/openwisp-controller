from functools import reduce


def _list_errors(e):
    """
    Returns a list of violated schema fragments and related error messages
    :param e: ``jsonschema.exceptions.ValidationError`` instance
    """
    error_list = []
    for value, error in zip(e.validator_value, e.context):
        error_list.append((value, error.message))
        if error.context:
            error_list += _list_errors(error)
    return error_list


class NetJsonConfigException(Exception):
    """
    Root netjsonconfig exception
    """

    def __str__(self):
        message = "%s %s\n" % (
            self.__class__.__name__,
            self.details,
        )
        errors = _list_errors(self.details)
        separator = "\nAgainst schema %s\n%s\n"
        details = reduce(lambda x, y: x + separator % y, errors, "")
        return message + details


class ValidationError(NetJsonConfigException):
    """
    Error while validating schema
    """

    def __init__(self, e):
        """
        preserve jsonschema exception attributes
        in self.details
        """
        self.message = e.message
        self.details = e


class ParseError(NetJsonConfigException):
    """
    Error while parsing native configuration
    """

    pass

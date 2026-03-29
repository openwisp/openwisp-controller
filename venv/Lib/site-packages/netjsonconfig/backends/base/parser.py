from netjsonconfig.exceptions import ParseError


class BaseParser(object):
    """
    Base Parser class
    Parsers are used to parse a string or tar.gz
    which represents the router configuration
    """

    def __init__(self, config):
        if isinstance(config, str):
            data = self.parse_text(config)
        # presence of read() method
        # indicates a file-like object
        elif hasattr(config, "read"):
            data = self.parse_tar(config)
        else:
            raise ParseError("Unrecognized format")
        self.intermediate_data = data

    def parse_text(self, config):
        raise NotImplementedError()

    def parse_tar(self, config):
        raise NotImplementedError()

from collections import OrderedDict

from ...utils import get_copy, sorted_dict


class BaseConverter(object):
    """
    Base Converter class
    Converters are used to convert a configuration dictionary
    which represent a NetJSON object to a data structure that
    can be easily rendered as the final router configuration
    and vice versa.
    """

    netjson_key = None
    intermediate_key = None

    def __init__(self, backend):
        self.backend = backend
        self.netjson = backend.config
        self.intermediate_data = backend.intermediate_data

    @classmethod
    def should_run_forward(cls, config):
        """
        Returns True if Converter should be instantiated and run
        during the forward conversion process (NetJSON to native)
        """
        return cls.netjson_key in config

    @classmethod
    def should_run_backward(cls, intermediate_data):
        """
        Returns True if Converter should be instantiated and run
        during the backward conversion process (native to NetJSON)
        """
        return cls.intermediate_key in intermediate_data

    def type_cast(self, item, schema=None):
        """
        Loops over item and performs type casting
        according to supplied schema fragment
        """
        if schema is None:
            schema = self._schema
        properties = schema["properties"]
        for key, value in item.items():
            if key not in properties:
                continue
            try:
                json_type = properties[key]["type"]
            except KeyError:
                json_type = None
            # if multiple types are supported, the first
            # one takes precedence when parsing
            if isinstance(json_type, list) and json_type:
                json_type = json_type[0]
            if json_type == "integer" and not isinstance(value, int):
                value = int(value)
            elif json_type == "boolean" and not isinstance(value, bool):
                value = value == "1"
            item[key] = value
        return item

    def get_copy(self, dict_, key, default=None):
        return get_copy(dict_, key, default)

    def sorted_dict(self, dict_):
        return sorted_dict(dict_)

    def to_intermediate(self):
        """
        Converts the NetJSON configuration dictionary (``self.config``)
        to intermediate data structure (``self.intermediate_datra``)
        """
        result = OrderedDict()
        # copy netjson dictionary
        netjson = get_copy(self.netjson, self.netjson_key)
        if isinstance(netjson, list):
            # iterate over copied netjson data structure
            for index, block in enumerate(netjson):
                result = self.to_intermediate_loop(block, result, index + 1)
        else:
            result = self.to_intermediate_loop(netjson, result)
        # return result, expects dict
        return result

    def to_intermediate_loop(self, block, result, index=None):  # pragma: nocover
        """
        Utility method called in the loop of ``to_intermediate``
        """
        raise NotImplementedError()

    def to_netjson(self, remove_block=True):
        """
        Converts the intermediate data structure (``self.intermediate_data``)
        to a NetJSON configuration dictionary (``self.config``)
        """
        result = OrderedDict()
        # clean intermediate data
        intermediate_data = self.to_netjson_clean(
            self.intermediate_data[self.intermediate_key]
        )
        # intermediate_data = list(self.intermediate_data[self.intermediate_key])
        # iterate over copied intermediate data structure
        for index, block in enumerate(intermediate_data):
            if self.should_skip_block(block):
                continue
            # remove processed block from intermediate data
            # this makes processing remaining blocks easier
            # for some backends
            if remove_block:
                self.intermediate_data[self.intermediate_key].remove(block)
            # specific converter operations are delegated
            # to the ``to_netjson_loop`` method
            result = self.to_netjson_loop(block, result, index + 1)
        # return result, expects dict
        return result

    def to_netjson_clean(self, intermediate_data):
        """
        Utility method called to pre-process the intermediate data structure
        during backward conversion (``to_netjson``)
        """
        # returns a copy in order to avoid modifying the original structure
        return list(intermediate_data)

    def to_netjson_loop(self, block, result, index=None):  # pragma: nocover
        """
        Utility method called in the loop of ``to_netjson``
        """
        raise NotImplementedError()

    def should_skip_block(self, block):
        return not block

import json
from collections import OrderedDict

from ....utils import sorted_dict
from .base import OpenWrtConverter


class Default(OpenWrtConverter):
    @classmethod
    def should_run_forward(cls, config):
        """Always runs"""
        return True

    @classmethod
    def should_run_backward(cls, intermediate_data):
        """Always runs"""
        return True

    def to_intermediate(self):
        # determine config keys to ignore
        ignore_list = list(self.backend.schema["properties"].keys())
        # determine extra packages used
        extra_packages = OrderedDict()
        for key, value in self.netjson.items():
            # skip blocks present in ignore_list
            # or blocks not represented by lists
            if key in ignore_list or not isinstance(value, list):
                continue
            block_list = []
            # sort each config block
            i = 1
            for block in list(value):
                # config block must be a dict
                # with a key named "config_name"
                # otherwise it's skipped with a warning
                if not isinstance(block, dict) or "config_name" not in block:
                    json_block = json.dumps(block, indent=4)
                    print(
                        "Unrecognized config block was skipped:\n\n"
                        "{0}\n\n".format(json_block)
                    )
                    continue
                block[".type"] = block.pop("config_name")
                block[".name"] = block.pop(
                    "config_value",
                    # default value in case the
                    # UCI name is not defined
                    "{0}_{1}".format(block[".type"], i),
                )
                # ensure UCI name is valid
                block[".name"] = self._get_uci_name(block[".name"])
                block_list.append(sorted_dict(block))
                i += 1
            if block_list:
                extra_packages[key] = block_list
        # sort result again to avoid test failures
        # related to the random order of dict keys
        return self.sorted_dict(extra_packages)

    def to_netjson(self):
        result = {}
        for package, contents in self.intermediate_data.items():
            if not contents:
                continue
            result.setdefault(package, [])
            for index, block in enumerate(contents):
                _name = block.pop(".name")
                _type = block.pop(".type")
                # set `config_value` only if it hasn't
                # been automatically generated
                if _name != "{0}_{1}".format(_type, index + 1):
                    block["config_value"] = _name
                block["config_name"] = _type
                result[package].append(block)
        return result

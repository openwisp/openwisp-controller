import re
import tarfile
from json import loads

from ..base.parser import BaseParser

vpn_pattern = re.compile(r"^// zerotier controller config:\s", flags=re.MULTILINE)
config_pattern = re.compile(r"^([^\s]*) ?(.*)$")
config_suffix = ".json"


class ZeroTierParser(BaseParser):
    def parse_text(self, config):
        return {"zerotier": self._get_vpn_config(config)}

    def parse_tar(self, tar):
        fileobj = tar.buffer if hasattr(tar, "buffer") else tar
        tar = tarfile.open(fileobj=fileobj)
        text = ""
        for member in tar.getmembers():
            if not member.name.endswith(config_suffix):
                continue
            text += "// zerotier controller config: {name}\n\n{contents}\n".format(
                **{
                    "name": member.name,
                    "contents": tar.extractfile(member).read().decode(),
                }
            )
        return self.parse_text(text)

    def _get_vpn_config(self, text):
        # Remove comments from the vpn text
        text = re.sub(r"\/\*(\*(?!\/)|[^*])*\*\/|\/\/.*", "", text)
        # Strip leading and trailing whitespace from the text
        text = text.strip()
        # Split the text into separate VPN instances
        # using two or more newline characters as the delimiter
        vpn_instances = re.split(r"\n{2,}", text)
        # Parse each JSON object separately
        vpn_configs = [
            loads(vpn_instance)
            for vpn_instance in vpn_instances
            if vpn_instance.strip()
        ]
        return vpn_configs

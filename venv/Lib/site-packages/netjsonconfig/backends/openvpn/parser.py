import re
import tarfile

from ...utils import sorted_dict
from ..base.parser import BaseParser

vpn_pattern = re.compile(r"^# openvpn config:\s", flags=re.MULTILINE)
config_pattern = re.compile(r"^([^\s]*) ?(.*)$")
config_suffix = ".conf"


class OpenVpnParser(BaseParser):
    def parse_text(self, config):
        return self._get_vpns(config)

    def parse_tar(self, tar):
        fileobj = tar.buffer if hasattr(tar, "buffer") else tar
        tar = tarfile.open(fileobj=fileobj)
        text = ""
        for member in tar.getmembers():
            if not member.name.endswith(config_suffix):
                continue
            text += "# openvpn config: {name}\n\n{contents}\n".format(
                **{
                    "name": member.name.replace(config_suffix, ""),
                    "contents": tar.extractfile(member).read().decode(),
                }
            )
        return self.parse_text(text)

    def _get_vpns(self, text):
        results = re.split(vpn_pattern, text)
        vpns = []
        for result in results:
            result = result.strip()
            if not result:
                continue
            vpns.append(self._get_config(result))
        return {"openvpn": vpns}

    def _get_config(self, contents):
        lines = contents.split("\n")
        name = lines[0]
        config = {"name": name}
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            match = re.search(config_pattern, line)
            parts = match.groups()
            key = parts[0].replace("-", "_")
            value = parts[1]
            if not value:
                value = True
            config[key] = value
        return sorted_dict(config)

import re

from jinja2 import Environment, PackageLoader

from ..openwrt.openwrt import OpenWrt
from .renderer import OpenWrtRenderer
from .schema import schema


class OpenWisp(OpenWrt):
    """
    OpenWISP 1.x Firmware (legacy) Configuration Backend
    """

    schema = schema
    renderer = OpenWrtRenderer

    def __init__(
        self, config=None, native=None, templates=None, context=None, dsa=False
    ):
        super().__init__(config, native, templates, context, dsa)

    def validate(self):
        self._sanitize_radios()
        super().validate()

    def _sanitize_radios(self):
        """
        OpenWisp 1.x requires the following explicit entry
        in the radio sections of /uci/wireless.conf:
            option disabled '0'
        """
        for radio in self.config.get("radios", []):
            radio.setdefault("disabled", False)

    def _render_template(self, template, context=None):
        openwisp_env = Environment(
            loader=PackageLoader(self.__module__, "templates"), trim_blocks=True
        )
        template = openwisp_env.get_template(template)
        context = context or {}
        return template.render(**context)

    def _add_unique_file(self, item):
        """
        adds a file in self.config['files'] only if not present already
        """
        if item not in self.config["files"]:
            self.config["files"].append(item)

    def _get_install_context(self):
        """
        returns the template context for install.sh and uninstall.sh
        """
        config = self.config
        # layer2 VPN list
        l2vpn = []
        for vpn in self.config.get("openvpn", []):
            if vpn.get("dev_type") != "tap":
                continue
            tap = vpn.copy()
            l2vpn.append(tap)
        # bridge list
        bridges = []
        for interface in self.config.get("interfaces", []):
            if interface["type"] != "bridge":
                continue
            bridge = interface.copy()
            if bridge.get("addresses"):
                bridge["proto"] = interface["addresses"][0].get("proto")
                bridge["ip"] = interface["addresses"][0].get("address")
            bridges.append(bridge)
        # crontabs present?
        cron = False
        for _file in config.get("files", []):
            path = _file["path"]
            if path.startswith("/crontabs") or path.startswith("crontabs"):
                cron = True
                break
        # return context
        return dict(
            hostname=config.get("general", {}).get("hostname", "OpenWISP1"),
            l2vpn=l2vpn,
            bridges=bridges,
            radios=config.get("radios", []),  # radios might be empty
            cron=cron,
        )

    def _add_install(self, context):
        """
        generates install.sh and adds it to included files
        """
        contents = self._render_template("install.sh", context)
        self.config.setdefault("files", [])  # file list might be empty
        # add install.sh to list of included files
        self._add_unique_file(
            {"path": "/install.sh", "contents": contents, "mode": "755"}
        )

    def _add_uninstall(self, context):
        """
        generates uninstall.sh and adds it to included files
        """
        contents = self._render_template("uninstall.sh", context)
        self.config.setdefault("files", [])  # file list might be empty
        # add uninstall.sh to list of included files
        self._add_unique_file(
            {"path": "/uninstall.sh", "contents": contents, "mode": "755"}
        )

    def _add_openvpn_scripts(self):
        l2vpn = []
        for vpn in self.config.get("openvpn", []):
            if vpn.get("dev_type") != "tap":
                continue
            tap = vpn.copy()
            if vpn.get("up"):
                tap["up"] = vpn["up"].split("/")[-1]
            if vpn.get("down"):
                tap["down"] = vpn["down"].split("/")[-1]
            l2vpn.append(tap)
        # add scripts
        for vpn in l2vpn:
            if vpn.get("up"):
                self._add_unique_file(
                    {
                        "path": "/openvpn/{0}".format(vpn["up"]),
                        "contents": self._render_template("vpn_script_up.sh"),
                        "mode": "755",
                    }
                )
            if vpn.get("down"):
                self._add_unique_file(
                    {
                        "path": "/openvpn/{0}".format(vpn["down"]),
                        "contents": self._render_template("vpn_script_down.sh"),
                        "mode": "755",
                    }
                )

    def _add_tc_script(self):
        """
        generates tc_script.sh and adds it to included files
        """
        # fill context
        context = dict(tc_options=self.config.get("tc_options", []))
        # import pdb; pdb.set_trace()
        contents = self._render_template("tc_script.sh", context)
        self.config.setdefault("files", [])  # file list might be empty
        # add tc_script.sh to list of included files
        self._add_unique_file(
            {"path": "/tc_script.sh", "contents": contents, "mode": "755"}
        )

    def _generate_contents(self, tar):
        """
        Adds configuration files to tarfile instance.

        :param tar: tarfile instance
        :returns: None
        """
        uci = self.render(files=False)
        # create a list with all the packages (and remove empty entries)
        packages = re.split("package ", uci)
        if "" in packages:
            packages.remove("")
        # create a file for each configuration package used
        for package in packages:
            lines = package.split("\n")
            package_name = lines[0]
            text_contents = "\n".join(lines[2:])
            text_contents = "package {0}\n\n{1}".format(package_name, text_contents)
            self._add_file(
                tar=tar,
                name="uci/{0}.conf".format(package_name),
                contents=text_contents,
            )
        # prepare template context for install and uninstall scripts
        template_context = self._get_install_context()
        # add install.sh to included files
        self._add_install(template_context)
        # add uninstall.sh to included files
        self._add_uninstall(template_context)
        # add vpn up and down scripts
        self._add_openvpn_scripts()
        # add tc_script
        self._add_tc_script()

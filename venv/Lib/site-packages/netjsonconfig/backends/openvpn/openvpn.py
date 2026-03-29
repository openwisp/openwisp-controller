from ...schema import X509_FILE_MODE
from ..base.backend import BaseVpnBackend
from . import converters
from .parser import OpenVpnParser, config_suffix, vpn_pattern
from .renderer import OpenVpnRenderer
from .schema import schema


class OpenVpn(BaseVpnBackend):
    """
    OpenVPN 2.x Configuration Backend
    """

    schema = schema
    converters = [converters.OpenVpn]
    parser = OpenVpnParser
    renderer = OpenVpnRenderer
    list_identifiers = ["name"]
    # BaseVpnBackend attributes
    vpn_pattern = vpn_pattern
    config_suffix = config_suffix

    @classmethod
    def auto_client(
        cls,
        host,
        server,
        ca_path=None,
        ca_contents=None,
        cert_path=None,
        cert_contents=None,
        key_path=None,
        key_contents=None,
    ):
        """
        Returns a configuration dictionary representing an OpenVPN client configuration
        that is compatible with the passed server configuration.

        :param host: remote VPN server
        :param server: dictionary representing a single OpenVPN server configuration
        :param ca_path: optional string representing path to CA, will consequently add
                        a file in the resulting configuration dictionary
        :param ca_contents: optional string representing contents of CA file
        :param cert_path: optional string representing path to certificate, will consequently add
                        a file in the resulting configuration dictionary
        :param cert_contents: optional string representing contents of cert file
        :param key_path: optional string representing path to key, will consequently add
                        a file in the resulting configuration dictionary
        :param key_contents: optional string representing contents of key file
        :returns: dictionary representing a single OpenVPN client configuration
        """
        # client defaults
        client = {
            "mode": "p2p",
            "nobind": True,
            "resolv_retry": "infinite",
            "tls_client": True,
        }
        # remote
        port = server.get("port") or 1195
        client["remote"] = [{"host": host, "port": port}]
        # proto
        if server.get("proto") == "tcp-server":
            client["proto"] = "tcp-client"
        else:
            client["proto"] = "udp"
        # determine if pull must be True
        if "server" in server or "server_bridge" in server:
            client["pull"] = True
        # tls_client
        if "tls_server" not in server or not server["tls_server"]:
            client["tls_client"] = False
        # ns_cert_type
        ns_cert_type = {None: "", "": "", "client": "server"}
        client["ns_cert_type"] = ns_cert_type[server.get("ns_cert_type")]
        # remote_cert_tls
        remote_cert_tls = {None: "", "": "", "client": "server"}
        client["remote_cert_tls"] = remote_cert_tls[server.get("remote_cert_tls")]
        tls_auth = server.get("tls_auth")
        if tls_auth:
            if len(tls_auth.strip().split(" ")) == 2:
                # The field contains path to auth key and direction.
                # auto_client does not support such format.
                pass
            else:
                # The TLS Auth key is present in the field.
                # Copy the TLS Auth key. Convertor will handle
                # parsing it into file.
                client["tls_auth"] = tls_auth
        copy_keys = [
            "name",
            "dev_type",
            "dev",
            "comp_lzo",
            "compress",
            "allow_compression",
            "auth",
            "cipher",
            "ca",
            "cert",
            "key",
            "pkcs12",
            "mtu_test",
            "fragment",
            "mssfix",
            "keepalive",
            "persist_tun",
            "mute",
            "persist_key",
            "user",
            "group",
            "mute_replay_warnings",
            "secret",
            "reneg_sec",
            "tls_timeout",
            "tls_cipher",
            "float",
            "fast_io",
            "verb",
            "auth_nocache",
        ]
        for key in copy_keys:
            if key in server:
                client[key] = server[key]
        if "script_security" in server:
            # From OpenWrt 21 onwards, "script_security" of "2"
            # is required for functioning of OpenVPN tunnels.
            client["script_security"] = 2
        if "log" in server:
            # The "/var/log/openvpn" directory is not present
            # on OpenWrt, hence the location of the log is changed.
            client["log"] = server["log"].replace("/var/log/openvpn/", "/var/log/")
        files = cls._auto_client_files(
            client,
            ca_path,
            ca_contents,
            cert_path,
            cert_contents,
            key_path,
            key_contents,
        )
        return {"openvpn": [client], "files": files}

    @classmethod
    def _auto_client_files(
        cls,
        client,
        ca_path=None,
        ca_contents=None,
        cert_path=None,
        cert_contents=None,
        key_path=None,
        key_contents=None,
    ):
        """
        returns a list of NetJSON extra files for automatically generated clients
        produces side effects in ``client`` dictionary
        """
        files = []
        if ca_path and ca_contents:
            client["ca"] = ca_path
            files.append(dict(path=ca_path, contents=ca_contents, mode=X509_FILE_MODE))
        if cert_path and cert_contents:
            client["cert"] = cert_path
            files.append(
                dict(path=cert_path, contents=cert_contents, mode=X509_FILE_MODE)
            )
        if key_path and key_contents:
            client["key"] = key_path
            files.append(
                dict(
                    path=key_path,
                    contents=key_contents,
                    mode=X509_FILE_MODE,
                )
            )
        return files

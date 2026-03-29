from .... import channels
from ..schema import default_radio_driver
from .base import OpenWrtConverter


class Radios(OpenWrtConverter):
    netjson_key = "radios"
    intermediate_key = "wireless"
    _uci_types = ["wifi-device"]

    def to_intermediate_loop(self, block, result, index=None):
        radio = self.__intermediate_radio(block)
        result.setdefault("wireless", [])
        result["wireless"].append(radio)
        return result

    def __intermediate_radio(self, radio):
        radio.update({".type": "wifi-device", ".name": radio.pop("name")})
        # rename tx_power to txpower
        if "tx_power" in radio:
            radio["txpower"] = radio.pop("tx_power")
        # rename driver to type
        radio["type"] = radio.pop("driver", default_radio_driver)
        self.__set_intermediate_band(radio)
        # check if using channel 0, that means "auto"
        if radio["channel"] == 0:
            radio["channel"] = "auto"
        # determine channel width
        if radio["type"] == "mac80211":
            radio["htmode"] = self.__intermediate_htmode(radio)
        else:
            del radio["protocol"]
        # ensure country is uppercase
        if "country" in radio:
            radio["country"] = radio["country"].upper()
        return self.sorted_dict(radio)

    def __set_intermediate_band(self, radio):
        if self.dsa:
            radio["band"] = self.__intermediate_band(radio)
        else:
            radio["hwmode"] = self.__intermediate_hwmode(radio)

    def __intermediate_band(self, radio):
        """
        Returns value for "band" option (introduced in OpenWrt 21)

        Backward compatibility: If the configuration defines
        "hwmode" instead of "band", then the value for "band" is inferred
        from "hwmode".

        If both "band" and "hwmode" are absent, then value for "band"
        is inferred from "protocal" or "channel".
        """
        hwmode = radio.pop("hwmode", None)
        band = radio.pop("band", None)
        if band:
            return band
        if hwmode:
            return self.__intermediate_band_from_hwmode(hwmode)
        channel = radio.get("channel")
        protocol = radio.get("protocol")
        # Infer radio frequency from protocol if possible
        if protocol == "802.11ad":
            return "60g"
        elif protocol in ["802.11b", "802.11g"]:
            return "2g"
        elif protocol in ["802.11a", "802.11ac"]:
            return "5g"
        # Infer radio frequency from channel of the radio
        if channel in channels.channels_2ghz:
            return "2g"
        elif channel in channels.channels_5ghz:
            return "5g"
        elif channel in channels.channels_6ghz:
            return "6g"

    def __intermediate_band_from_hwmode(self, hwmode):
        # Using "hwmode" we can only predict 2GHz and 5GHz radios.
        # Support for 802.11ax (2/5/6 GHz) and 802.11ad (60 GHz)
        # was added in OpenWrt 21.
        if hwmode == "11a":
            return "5g"
        elif hwmode in ["11b", "11g"]:
            return "2g"

    def __intermediate_hwmode(self, radio):
        """
        Returns value for "hwmode" option (OpenWrt < 21)

        Backward compatibility: If the configuration defines
        "band" (introduced in OpenWrt 21) instead of "hwmode",
        then the value for "hwmode" is inferred from "band".
        """
        hwmode = radio.pop("hwmode", None)
        band = radio.pop("band", None)
        if hwmode:
            return hwmode
        if band:
            # 802.11ax and 802.11ad were not supported in OpenWrt < 21.
            # Hence, we ignore "6g" and "60g" values.
            if band == "2g":
                if radio["protocol"] == "802.11b":
                    return "11b"
                else:
                    return "11g"
            elif band == "5g":
                return "11a"
        # Use protocol to infer "hwmode"
        protocol = radio["protocol"]
        if protocol in ["802.11a", "802.11b", "802.11g"]:
            # return 11a, 11b or 11g
            return protocol[4:]
        if protocol == "802.11ac":
            return "11a"
        # determine hwmode depending on channel used
        if radio["channel"] == 0:
            # when using automatic channel selection, we need an
            # additional parameter to determine the frequency band
            return radio.get("hwmode")
        elif radio["channel"] <= 13:
            return "11g"
        else:
            return "11a"

    def __intermediate_htmode(self, radio):
        """
        only for mac80211 driver
        """
        protocol = radio.pop("protocol")
        channel_width = radio.pop("channel_width")
        # allow overriding htmode
        if "htmode" in radio:
            return radio["htmode"]
        if protocol == "802.11n":
            return "HT{0}".format(channel_width)
        elif protocol == "802.11ac":
            return "VHT{0}".format(channel_width)
        elif protocol == "802.11ax":
            return "HE{0}".format(channel_width)
        # disables n
        return "NONE"

    def to_netjson_loop(self, block, result, index):
        radio = self.__netjson_radio(block)
        result.setdefault("radios", [])
        result["radios"].append(radio)
        return result

    def __netjson_radio(self, radio):
        del radio[".type"]
        radio["name"] = radio.pop(".name")
        if "txpower" in radio:
            radio["tx_power"] = int(radio.pop("txpower"))
        radio["driver"] = radio.pop("type")
        if "disabled" in radio:
            radio["disabled"] = radio["disabled"] == "1"
        radio["protocol"] = self.__netjson_protocol(radio)
        radio["channel"] = self.__netjson_channel(radio)
        radio["channel_width"] = self.__netjson_channel_width(radio)
        return radio

    def __netjson_protocol(self, radio):
        """
        determines NetJSON protocol radio attribute
        """
        htmode = radio.get("htmode")
        if htmode.startswith("HT"):
            return "802.11n"
        elif htmode.startswith("VHT"):
            return "802.11ac"
        elif htmode.startswith("HE"):
            return "802.11ax"
        elif htmode == "NONE":
            band = radio.get("band")
            if self.dsa and band:
                band_map = {"2g": "802.11g", "5g": "802.11a", "60g": "802.11ad"}
                return band_map[band]
            else:
                hwmode = radio.get("hwmode", None)
                return "802.{0}".format(hwmode)

    def __netjson_channel(self, radio):
        """
        determines NetJSON channel radio attribute
        """
        if radio["channel"] == "auto":
            return 0
        # delete hwmode because is needed
        # only when channel is auto
        radio.pop("hwmode", None)
        return int(radio["channel"])

    def __netjson_channel_width(self, radio):
        """
        determines NetJSON channel_width radio attribute
        """
        htmode = radio.pop("htmode")
        if htmode == "NONE":
            return 20
        channel_width = htmode.replace("VHT", "").replace("HT", "").replace("HE", "")
        # we need to override htmode
        if "+" in channel_width or "-" in channel_width:
            radio["htmode"] = htmode
            channel_width = channel_width[0:-1]
        return int(channel_width)

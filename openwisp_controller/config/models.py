import swapper

from .base.config import AbstractConfig
from .base.device import AbstractDevice
from .base.device_group import AbstractDeviceGroup
from .base.multitenancy import (
    AbstractOrganizationConfigSettings,
    AbstractOrganizationLimits,
)
from .base.tag import AbstractTaggedTemplate, AbstractTemplateTag
from .base.template import AbstractTemplate
from .base.vpn import AbstractVpn, AbstractVpnClient
from .base.whois import AbstractWHOISInfo


class Device(AbstractDevice):
    """
    Concrete Device model
    """

    class Meta(AbstractDevice.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "Device")


class DeviceGroup(AbstractDeviceGroup):
    """
    Concrete DeviceGroup model
    """

    class Meta(AbstractDeviceGroup.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "DeviceGroup")


class Config(AbstractConfig):
    """
    Concrete Config model
    """

    class Meta(AbstractConfig.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "Config")


class TemplateTag(AbstractTemplateTag):
    """
    openwisp-controller TemplateTag model
    """

    class Meta(AbstractTemplateTag.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "TemplateTag")


class TaggedTemplate(AbstractTaggedTemplate):
    """
    openwisp-controller TaggedTemplate model
    """

    class Meta(AbstractTaggedTemplate.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "TaggedTemplate")


class Template(AbstractTemplate):
    """
    openwisp-controller Template model
    """

    class Meta(AbstractTemplate.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "Template")


class Vpn(AbstractVpn):
    """
    openwisp-controller VPN model
    """

    class Meta(AbstractVpn.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "Vpn")


class VpnClient(AbstractVpnClient):
    """
    m2m through model
    """

    class Meta(AbstractVpnClient.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "VpnClient")


class OrganizationConfigSettings(AbstractOrganizationConfigSettings):
    """
    Configuration management settings
    specific to each organization
    """

    class Meta(AbstractOrganizationConfigSettings.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "OrganizationConfigSettings")


class OrganizationLimits(AbstractOrganizationLimits):
    """
    Number of allowed devices specific to each organization
    """

    class Meta(AbstractOrganizationLimits.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "OrganizationLimits")


class WHOISInfo(AbstractWHOISInfo):
    """
    Stores WHOIS information for devices.
    """

    class Meta(AbstractWHOISInfo.Meta):
        abstract = False
        swappable = swapper.swappable_setting("config", "WHOISInfo")

from .base.config import AbstractConfig
from .base.device import AbstractDevice
from .base.multitenancy import AbstractOrganizationConfigSettings
from .base.tag import AbstractTaggedTemplate, AbstractTemplateTag
from .base.template import AbstractTemplate
from .base.vpn import AbstractVpn, AbstractVpnClient


class Device(AbstractDevice):
    """
    Concrete Device model
    """

    class Meta(AbstractDevice.Meta):
        abstract = False


class Config(AbstractConfig):
    """
    Concrete Config model
    """

    class Meta(AbstractConfig.Meta):
        abstract = False


class TemplateTag(AbstractTemplateTag):
    """
    openwisp-controller TemplateTag model
    """

    class Meta(AbstractTemplateTag.Meta):
        abstract = False


class TaggedTemplate(AbstractTaggedTemplate):
    """
    openwisp-controller TaggedTemplate model
    """

    class Meta(AbstractTaggedTemplate.Meta):
        abstract = False


class Template(AbstractTemplate):
    """
    openwisp-controller Template model
    """

    class Meta(AbstractTemplate.Meta):
        abstract = False


class Vpn(AbstractVpn):
    """
    openwisp-controller VPN model
    """

    class Meta(AbstractVpn.Meta):
        abstract = False


class VpnClient(AbstractVpnClient):
    """
    m2m through model
    """

    class Meta(AbstractVpnClient.Meta):
        abstract = False


class OrganizationConfigSettings(AbstractOrganizationConfigSettings):
    """
    Configuration management settings
    specific to each organization
    """

    class Meta(AbstractOrganizationConfigSettings.Meta):
        abstract = False

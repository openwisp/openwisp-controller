from django.db import models

from openwisp_controller.config.base.config import AbstractConfig
from openwisp_controller.config.base.device import AbstractDevice
from openwisp_controller.config.base.device_group import AbstractDeviceGroup
from openwisp_controller.config.base.multitenancy import (
    AbstractOrganizationConfigSettings,
    AbstractOrganizationLimits,
)
from openwisp_controller.config.base.tag import (
    AbstractTaggedTemplate,
    AbstractTemplateTag,
)
from openwisp_controller.config.base.template import AbstractTemplate
from openwisp_controller.config.base.vpn import AbstractVpn, AbstractVpnClient
from openwisp_controller.config.base.whois import AbstractWHOISInfo


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        abstract = True


class Device(DetailsModel, AbstractDevice):
    """
    Concrete Device model
    """

    class Meta(AbstractDevice.Meta):
        abstract = False


class DeviceGroup(DetailsModel, AbstractDeviceGroup):
    """
    Concrete Device model
    """

    class Meta(AbstractDeviceGroup.Meta):
        abstract = False


class Config(DetailsModel, AbstractConfig):
    """
    Concrete Config model
    """

    class Meta(AbstractConfig.Meta):
        abstract = False


class TemplateTag(DetailsModel, AbstractTemplateTag):
    """
    openwisp-controller TemplateTag model
    """

    class Meta(AbstractTemplateTag.Meta):
        abstract = False


class TaggedTemplate(DetailsModel, AbstractTaggedTemplate):
    """
    openwisp-controller TaggedTemplate model
    """

    class Meta(AbstractTaggedTemplate.Meta):
        abstract = False


class Template(DetailsModel, AbstractTemplate):
    """
    openwisp-controller Template model
    """

    class Meta(AbstractTemplate.Meta):
        abstract = False


class Vpn(DetailsModel, AbstractVpn):
    """
    openwisp-controller VPN model
    """

    class Meta(AbstractVpn.Meta):
        abstract = False


class VpnClient(DetailsModel, AbstractVpnClient):
    """
    m2m through model
    """

    class Meta(AbstractVpnClient.Meta):
        abstract = False


class OrganizationConfigSettings(DetailsModel, AbstractOrganizationConfigSettings):
    """
    Configuration management settings
    specific to each organization
    """

    class Meta(AbstractOrganizationConfigSettings.Meta):
        abstract = False


class OrganizationLimits(DetailsModel, AbstractOrganizationLimits):
    """
    Number of allowed devices specific to each organization
    """

    class Meta(AbstractOrganizationLimits.Meta):
        abstract = False


class WHOISInfo(DetailsModel, AbstractWHOISInfo):
    """
    Stores WHOIS information for devices.
    """

    class Meta(AbstractWHOISInfo.Meta):
        abstract = False

from django.contrib.auth import get_user_model
from django.test import TestCase

from ...pki.models import Ca, Cert
from ..models import (
    Config,
    Device,
    OrganizationConfigSettings,
    Template,
    Vpn,
    VpnClient,
)
from .base.test_admin import AbstractTestAdmin
from .base.test_config import AbstractTestConfig
from .base.test_controller import AbstractTestController
from .base.test_device import AbstractTestDevice
from .base.test_tag import AbstractTestTag
from .base.test_template import AbstractTestTemplate
from .base.test_views import AbstractTestViews
from .base.test_vpn import AbstractTestVpn


class TestAdmin(AbstractTestAdmin, TestCase):
    ca_model = Ca
    cert_model = Cert
    config_model = Config
    device_model = Device
    template_model = Template
    vpn_model = Vpn
    user_model = get_user_model()


class TestConfig(AbstractTestConfig, TestCase):
    config_model = Config
    device_model = Device
    template_model = Template
    ca_model = Ca
    vpn_model = Vpn


class TestController(AbstractTestController, TestCase):
    config_model = Config
    device_model = Device
    template_model = Template
    org_config_set_model = OrganizationConfigSettings
    ca_model = Ca
    vpn_model = Vpn


class TestDevice(AbstractTestDevice, TestCase):
    config_model = Config
    device_model = Device


class TestTag(AbstractTestTag, TestCase):
    template_model = Template


class TestTemplate(AbstractTestTemplate, TestCase):
    ca_model = Ca
    cert_model = Cert
    config_model = Config
    device_model = Device
    template_model = Template
    vpn_model = Vpn
    user_model = get_user_model()


class TestViews(AbstractTestViews, TestCase):
    template_model = Template
    user_model = get_user_model()


class TestVpn(AbstractTestVpn, TestCase):
    ca_model = Ca
    cert_model = Cert
    vpn_model = Vpn
    vpn_client_model = VpnClient
    template_model = Template
    device_model = Device
    config_model = Config

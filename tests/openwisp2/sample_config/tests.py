from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from openwisp_controller.config import settings as app_settings
from openwisp_controller.config.tests.test_admin import TestAdmin as BaseTestAdmin
from openwisp_controller.config.tests.test_admin import (
    TestDeviceGroupAdmin as BaseTestDeviceGroupAdmin,
)
from openwisp_controller.config.tests.test_admin import (
    TestDeviceGroupAdminTransaction as BaseTestDeviceGroupAdminTransaction,
)
from openwisp_controller.config.tests.test_admin import (
    TestTransactionAdmin as BaseTestTransactionAdmin,
)
from openwisp_controller.config.tests.test_api import TestConfigApi as BaseTestConfigApi
from openwisp_controller.config.tests.test_apps import TestApps as BaseTestApps
from openwisp_controller.config.tests.test_config import TestConfig as BaseTestConfig
from openwisp_controller.config.tests.test_config import (
    TestTransactionConfig as BaseTestTransactionConfig,
)
from openwisp_controller.config.tests.test_controller import (
    TestController as BaseTestController,
)
from openwisp_controller.config.tests.test_device import TestDevice as BaseTestDevice
from openwisp_controller.config.tests.test_device_group import (
    TestDeviceGroup as BaseTestDeviceGroup,
)
from openwisp_controller.config.tests.test_notifications import (
    TestNotifications as BaseTestNotifications,
)
from openwisp_controller.config.tests.test_tag import TestTag as BaseTestTag
from openwisp_controller.config.tests.test_template import (
    TestTemplate as BaseTestTemplate,
)
from openwisp_controller.config.tests.test_template import (
    TestTemplateTransaction as BaseTestTemplateTransaction,
)
from openwisp_controller.config.tests.test_views import TestViews as BaseTestViews
from openwisp_controller.config.tests.test_vpn import TestVpn as BaseTestVpn
from openwisp_controller.config.tests.test_vpn import (
    TestVpnTransaction as BaseTestVpnTransaction,
)
from openwisp_controller.config.tests.test_vpn import TestVxlan as BaseTestVxlan
from openwisp_controller.config.tests.test_vpn import TestWireguard as BaseTestWireguard
from openwisp_controller.config.whois.service import WHOISService
from openwisp_controller.config.whois.tests.tests import TestWHOIS as BaseTestWHOIS
from openwisp_controller.config.whois.tests.utils import CreateWHOISMixin
from openwisp_controller.config.whois.utils import get_whois_info
from openwisp_controller.tests.utils import LOCAL_MEMORY_CACHE, TestAdminMixin


class TestAdmin(BaseTestAdmin):
    app_label = "sample_config"


class TestTransactionAdmin(BaseTestTransactionAdmin):
    app_label = "sample_config"
    _deactivated_device_expected_readonly_fields = 23


class TestDeviceGroupAdmin(BaseTestDeviceGroupAdmin):
    app_label = "sample_config"


class TestDeviceGroupAdminTransaction(BaseTestDeviceGroupAdminTransaction):
    app_label = "sample_config"


class TestConfig(BaseTestConfig):
    pass


class TestTransactionConfig(BaseTestTransactionConfig):
    pass


class TestController(BaseTestController):
    pass


class TestDevice(BaseTestDevice):
    pass


class TestDeviceGroup(BaseTestDeviceGroup):
    pass


class TestTag(BaseTestTag):
    pass


class TestTemplate(BaseTestTemplate):
    pass


class TestTemplateTransaction(BaseTestTemplateTransaction):
    pass


class TestNotifications(BaseTestNotifications):
    app_label = "sample_config"


class TestViews(BaseTestViews):
    pass


class TestVpn(BaseTestVpn):
    pass


class TestVpnTransaction(BaseTestVpnTransaction):
    pass


class TestApps(BaseTestApps):
    pass


class TestConfigApi(BaseTestConfigApi):
    pass


class TestWireguard(BaseTestWireguard):
    pass


class TestVxlan(BaseTestVxlan):
    pass


@override_settings(CACHES=LOCAL_MEMORY_CACHE)
class TestWHOIS(CreateWHOISMixin, TestAdminMixin, TestCase):
    test_approximate_whois_does_not_expose_other_organization_ip = (
        BaseTestWHOIS.test_approximate_whois_does_not_expose_other_organization_ip
    )

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_approximate_whois_excludes_custom_fields(self):
        source = self._create_whois_info(
            details="private organization data",
            address={"country": "United States", "private": "private address data"},
        )
        other_org = self._get_org("other")
        self._create_device(organization=other_org, last_ip=source.ip_address)
        device = self._create_device(last_ip="172.217.22.15")
        operator = self._create_operator(organizations=[device.organization])
        self.client.force_login(operator)
        cache.set(WHOISService.get_quota_cache_key(), timezone.now().timestamp() + 3600)
        response = self.client.get(
            reverse("admin:sample_config_device_change", args=[device.pk])
        )
        self.assertContains(response, '"approximate": true')
        self.assertNotContains(response, "private organization data")
        self.assertNotContains(response, "private address data")
        self.assertNotIn("details", get_whois_info(device.pk))
        exact_device = self._create_device(
            name="exact-device", mac_address="00:11:22:33:44:66", last_ip=source.pk
        )
        self.assertEqual(get_whois_info(exact_device.pk)["details"], source.details)


del BaseTestAdmin
del BaseTestTransactionAdmin
del BaseTestDeviceGroupAdmin
del BaseTestDeviceGroupAdminTransaction
del BaseTestConfig
del BaseTestTransactionConfig
del BaseTestController
del BaseTestDevice
del BaseTestDeviceGroup
del BaseTestTag
del BaseTestTemplate
del BaseTestTemplateTransaction
del BaseTestNotifications
del BaseTestViews
del BaseTestVpn
del BaseTestVpnTransaction
del BaseTestApps
del BaseTestConfigApi
del BaseTestWireguard
del BaseTestVxlan
del BaseTestWHOIS

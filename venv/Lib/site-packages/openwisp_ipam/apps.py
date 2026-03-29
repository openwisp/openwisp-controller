from django.utils.translation import gettext_lazy as _
from openwisp_utils.admin_theme.menu import register_menu_group
from openwisp_utils.api.apps import ApiAppConfig
from openwisp_utils.utils import default_or_test
from swapper import get_model_name


class OpenWispIpamConfig(ApiAppConfig):
    name = "openwisp_ipam"
    verbose_name = "IPAM"

    API_ENABLED = True
    REST_FRAMEWORK_SETTINGS = {
        "DEFAULT_THROTTLE_RATES": {"ipam": default_or_test("400/hour", None)},
    }

    def ready(self, *args, **kwargs):
        super().ready(*args, **kwargs)
        self.register_menu_groups()

    def register_menu_groups(self):
        register_menu_group(
            position=90,
            config={
                "label": _("Ipam"),
                "items": {
                    1: {
                        "label": _("IP Addresses"),
                        "model": get_model_name("openwisp_ipam", "IpAddress"),
                        "name": "changelist",
                        "icon": "ow-ip-address",
                    },
                    2: {
                        "label": _("Subnets"),
                        "model": get_model_name("openwisp_ipam", "Subnet"),
                        "name": "changelist",
                        "icon": "ow-subnet",
                    },
                },
                "icon": "ow-ipam",
            },
        )


del ApiAppConfig

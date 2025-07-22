from swapper import load_model

from ..tests.utils import CreateConfigMixin

Device = load_model("config", "Device")
WHOISInfo = load_model("config", "WHOISInfo")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")


class CreateWHOISMixin(CreateConfigMixin):
    def _create_whois_info(self, **kwargs):
        options = dict(
            ip_address="172.217.22.14",
            address={
                "city": "Mountain View",
                "country": "United States",
                "continent": "North America",
                "postal": "94043",
            },
            asn="15169",
            isp="Google LLC",
            timezone="America/Los_Angeles",
            cidr="172.217.22.0/24",
        )

        options.update(kwargs)
        w = WHOISInfo(**options)
        w.full_clean()
        w.save()
        return w

    def setUp(self):
        super().setUp()
        OrganizationConfigSettings.objects.create(
            organization=self._get_org(), whois_enabled=True
        )

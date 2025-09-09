from swapper import load_model

from openwisp_controller.config.whois.tests.utils import CreateWHOISMixin

OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")


class TestEstimatedLocationMixin(CreateWHOISMixin):
    def setUp(self):
        super(CreateWHOISMixin, self).setUp()
        OrganizationConfigSettings.objects.create(
            organization=self._get_org(),
            whois_enabled=True,
            estimated_location_enabled=True,
        )

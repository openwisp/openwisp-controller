from swapper import load_model

from openwisp_controller.config.whois.tests.utils import CreateWHOISMixin

from ..tasks import manage_estimated_locations

OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")


class TestEstimatedLocationMixin(CreateWHOISMixin):
    def setUp(self):
        # skip the org config settings creation from the parent mixin
        super(CreateWHOISMixin, self).setUp()
        OrganizationConfigSettings.objects.create(
            organization=self._get_org(),
            whois_enabled=True,
            estimated_location_enabled=True,
        )

    # helper to mock send_task to directly call the task function
    @staticmethod
    def run_task(name, args=None, kwargs=None, **_):
        assert name == "whois_estimated_location_task"
        return manage_estimated_locations(*args or [], **kwargs or {})

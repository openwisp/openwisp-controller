from swapper import load_model

from openwisp_controller.config.whois.tasks import fetch_whois_details
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

    # helper to mock send_task to directly call the task function synchronously
    @staticmethod
    def run_task(name, args=None, kwargs=None, **_):
        # This mock intercepts all Celery send_task calls and executes them
        # synchronously for testing purposes. We need to handle both task names
        # because when a device is created/saved, the WHOIS lookup task may be
        # triggered first, which then triggers the estimated location task.
        # Without handling both, the assertion would fail and break the test flow.
        if name == "whois_estimated_location_task":
            return manage_estimated_locations(*args or [], **kwargs or {})
        elif name == "openwisp_controller.config.whois.tasks.fetch_whois_details":
            return fetch_whois_details(*args or [], **kwargs or {})
        # Let other tasks pass through (they may be mocked elsewhere)
        return None

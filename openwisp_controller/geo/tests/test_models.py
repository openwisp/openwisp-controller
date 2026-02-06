import swapper
from django.core.exceptions import ValidationError
from django.test import TestCase
from django_loci.tests.base import test_models as loci_test_models
from swapper import load_model

from .utils import TestGeoMixin

Device = load_model("config", "Device")
Location = load_model("geo", "Location")
FloorPlan = load_model("geo", "FloorPlan")
DeviceLocation = load_model("geo", "DeviceLocation")


class TestModels(TestGeoMixin, loci_test_models.BaseTestModels, TestCase):
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = DeviceLocation

    def test_floorplan_location_validation(self):
        fl = self._create_floorplan()
        fl.location = None
        self.assertFalse(hasattr(fl, "location"))
        try:
            fl.full_clean()
        except ValidationError as e:
            self.assertIn("location", e.message_dict)
        else:
            self.fail("ValidationError not raised")

    def test_floorplan_org_updates_when_location_org_changes(self):
        Organization = swapper.load_model("openwisp_users", "Organization")

        # This helper creates a floorplan with a valid (indoor) location
        floorplan = self._create_floorplan()
        location = floorplan.location

        # sanity: floorplan org matches location org initially
        self.assertEqual(floorplan.organization_id, location.organization_id)

        org_b = Organization.objects.create(name="org-b", slug="org-b")
        location.organization = org_b
        location.save()

        floorplan.refresh_from_db()
        self.assertEqual(floorplan.organization_id, org_b.id)

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils.deprecation import RemovedInDjango60Warning
from django_loci.tests.base.test_models import BaseTestModels
from swapper import load_model

from .utils import TestGeoMixin

Device = load_model("config", "Device")
Location = load_model("geo", "Location")
FloorPlan = load_model("geo", "FloorPlan")
DeviceLocation = load_model("geo", "DeviceLocation")


class TestModels(TestGeoMixin, BaseTestModels, TestCase):
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

    def test_location_organization_updates_floorplans(self):
        location = self._create_location(type="indoor")
        floorplans = [
            self._create_floorplan(location=location, floor=floor) for floor in (1, 2)
        ]
        unrelated = self._create_floorplan()
        original_org = unrelated.organization_id
        organization = self._create_organization(name="second")
        location.organization = organization
        location.full_clean()
        location.save()
        for floorplan in floorplans:
            floorplan.refresh_from_db()
            self.assertEqual(floorplan.organization_id, organization.pk)
        unrelated.refresh_from_db()
        self.assertEqual(unrelated.organization_id, original_org)

    def test_location_organization_partial_save(self):
        location = self._create_location(type="indoor")
        floorplan = self._create_floorplan(location=location)
        original_org = location.organization_id
        organization = self._create_organization(name="second")
        location.organization = organization
        location.name = "renamed"
        location.save(update_fields=["name"])
        floorplan.refresh_from_db()
        self.assertEqual(floorplan.organization_id, original_org)
        self.assertEqual(
            Location.objects.get(pk=location.pk).organization_id, original_org
        )
        location.save(update_fields=["organization"])
        floorplan.refresh_from_db()
        self.assertEqual(floorplan.organization_id, organization.pk)

    def test_location_organization_deferred(self):
        location = self._create_location(type="indoor")
        floorplan = self._create_floorplan(location=location)
        location = Location.objects.defer("organization").get(pk=location.pk)
        organization = self._create_organization(name="second")
        location.organization = organization
        location.save(update_fields=["organization_id"])
        floorplan.refresh_from_db()
        self.assertEqual(floorplan.organization_id, organization.pk)

    def test_location_unchanged_organization(self):
        location = self._create_location(type="indoor")
        floorplan = self._create_floorplan(location=location)
        for update_fields in (None, [], ["name"]):
            with self.subTest(update_fields=update_fields):
                location.name = "renamed"
                with CaptureQueriesContext(connection) as queries:
                    location.save(update_fields=update_fields)
                self.assertFalse(
                    any(
                        query["sql"].startswith("UPDATE")
                        and FloorPlan._meta.db_table in query["sql"]
                        for query in queries
                    ),
                    "Saving an unchanged organization must not update floorplans",
                )
                floorplan.refresh_from_db()
                self.assertEqual(floorplan.organization_id, location.organization_id)

    def test_location_organization_positional_save(self):
        location = self._create_location(type="indoor")
        floorplan = self._create_floorplan(location=location)
        original_org = location.organization_id
        organization = self._create_organization(name="second")
        location.organization = organization
        with self.assertWarns(RemovedInDjango60Warning):
            location.save(False, False, None, ["name"])
        floorplan.refresh_from_db()
        self.assertEqual(floorplan.organization_id, original_org)
        with self.assertWarns(RemovedInDjango60Warning):
            location.save(False, False, None, ["organization"])
        floorplan.refresh_from_db()
        self.assertEqual(floorplan.organization_id, organization.pk)

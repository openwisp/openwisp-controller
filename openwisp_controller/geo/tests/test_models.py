from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
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
        with patch(
            "django.db.router.db_for_write", return_value=connection.alias
        ) as db:
            location.save()
        db.assert_called_once_with(Location, instance=location)
        for floorplan in floorplans:
            floorplan.refresh_from_db()
            self.assertEqual(floorplan.organization_id, organization.pk)
        unrelated.refresh_from_db()
        self.assertEqual(unrelated.organization_id, original_org)

    def test_location_organization_update_rollback(self):
        location = self._create_location(type="indoor")
        floorplan = self._create_floorplan(location=location)
        original_org = location.organization_id
        organization = self._create_organization(name="second")
        location.organization = organization
        with patch.object(
            type(FloorPlan.objects.all()),
            "update",
            side_effect=RuntimeError("floorplan update failed"),
        ):
            with self.assertRaisesMessage(RuntimeError, "floorplan update failed"):
                location.save(using=connection.alias)
        self.assertEqual(
            Location.objects.get(pk=location.pk).organization_id,
            original_org,
            "A failed floorplan update must roll back the location organization",
        )
        floorplan.refresh_from_db()
        self.assertEqual(floorplan.organization_id, original_org)

    def test_location_partial_and_stale_saves(self):
        location = self._create_location(type="indoor")
        floorplan = self._create_floorplan(location=location)
        original_org = location.organization_id
        stale = Location.objects.get(pk=location.pk)
        organization = self._create_organization(name="second")
        location.organization_id = organization.pk
        location.save(update_fields=["organization_id"])

        for fields in (["name"], []):
            with self.subTest(update_fields=fields):
                stale.save(update_fields=iter(fields))
                location.refresh_from_db()
                floorplan.refresh_from_db()
                self.assertEqual(location.organization_id, organization.pk)
                self.assertEqual(floorplan.organization_id, organization.pk)

        stale.save()
        location.refresh_from_db()
        floorplan.refresh_from_db()
        self.assertEqual(location.organization_id, original_org)
        self.assertEqual(floorplan.organization_id, original_org)

    def test_location_positional_organization_save(self):
        location = self._create_location(type="indoor")
        floorplan = self._create_floorplan(location=location)
        organization = self._create_organization(name="second")
        location.organization = organization
        with patch("django.db.router.db_for_write") as db:
            location.save(False, False, connection.alias, iter(["organization"]))
        db.assert_not_called()
        location.refresh_from_db()
        floorplan.refresh_from_db()
        self.assertEqual(location.organization_id, organization.pk)
        self.assertEqual(floorplan.organization_id, organization.pk)

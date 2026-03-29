from django.core.exceptions import ValidationError

from .. import TestLociMixin


class BaseTestModels(TestLociMixin):
    def test_location_str(self):
        loc = self.location_model(name="test-location")
        self.assertEqual(str(loc), loc.name)

    def test_floorplan_str(self):
        loc = self._create_location()
        fl = self.floorplan_model(location=loc, floor=2)
        self.assertEqual(str(fl), "test-location 2nd floor")
        fl.floor = 0
        self.assertEqual(str(fl), "test-location ground floor")

    def test_object_location_clean_location(self):
        l1 = self._create_location(type="indoor")
        l2 = self._create_location(type="indoor")
        fl2 = self._create_floorplan(location=l2)
        obj = self._create_object()
        ol = self.object_location_model(content_object=obj, location=l1, floorplan=fl2)
        try:
            ol.full_clean()
        except ValidationError as e:
            self.assertIn("__all__", e.message_dict)
            self.assertEqual(
                e.message_dict.get("__all__")[0],
                "Invalid floorplan (belongs to a different location)",
            )
        else:
            self.fail("ValidationError not raised")

    def test_floorplan_image(self):
        fl = self._create_floorplan()
        path = fl.image.file.name.split("/")
        name = path[-1]
        dir_ = path[-2]
        self.assertEqual(name, "{0}.jpg".format(fl.id))
        self.assertEqual(dir_, "floorplans")
        # overwrite
        fl.image = self._get_simpleuploadedfile()
        fl.full_clean()
        fl.save()
        path = fl.image.file.name.split("/")
        name = path[-1]
        dir_ = path[-2]
        self.assertEqual(name, "{0}.jpg".format(fl.id))
        self.assertEqual(dir_, "floorplans")
        # delete
        image_path = fl.image.file.name
        fl.delete()
        self.assertFalse(fl.image.storage.exists(image_path))

    def test_floorplan_delete_corner_case(self):
        fl = self._create_floorplan()
        fl.image.storage.delete(fl.image.file.name)
        # there should be no failure
        fl.delete()

    def test_floorplan_association_validation(self):
        outdoor = self._create_location(type="outdoor")
        try:
            self._create_floorplan(location=outdoor)
        except ValidationError as e:
            err_str = str(e)
            self.assertIn("floorplans can only be associated to", err_str)
            self.assertIn("indoor", err_str)
        else:
            self.fail("ValidationError not raised")

    def test_geometry_if_not_mobile(self):
        try:
            self._create_location(geometry=None)
        except ValidationError as e:
            err_str = str(e)
            self.assertIn("No geometry value provided.", err_str)
        else:
            self.fail("ValidationError not raised")

    def test_geometry_if_mobile(self):
        try:
            self._create_location(is_mobile=True, geometry=None)
        except ValidationError:
            self.fail("Unexpected ValidationError raised")

    # changing location type from indoor to outdoor, deletes floorplans
    def test_location_change_indoor_to_outdoor(self):
        fl = self._create_floorplan()
        location = fl.location
        location.type = "outdoor"
        location.save()
        self.assertEqual(location.floorplan_set.count(), 0)

    # similar to 'test_location_change_indoor_to_outdoor' but with object location
    def test_object_location_change_indoor_to_outdoor(self):
        l1 = self._create_location(type="indoor")
        fl = self._create_floorplan(location=l1)
        obj = self._create_object()
        ol = self.object_location_model(
            content_object=obj, location=l1, floorplan=fl, indoor="-100,100"
        )
        ol.full_clean()
        ol.save()
        l1.type = "outdoor"
        l1.save()
        # refetching again to check if object location is updated
        ol = self.object_location_model.objects.get(pk=ol.pk)
        self.assertIsNone(ol.floorplan)
        self.assertIsNone(ol.indoor)
        self.assertEqual(ol.location.type, "outdoor")
        self.assertEqual(ol.location.floorplan_set.count(), 0)

    def _test_indoor_position_validation_error(self, ol):
        try:
            ol.full_clean()
        except ValidationError as e:
            self.assertIn("indoor", e.message_dict)
            self.assertIn("invalid value", e.message_dict["indoor"])
        else:
            self.fail("ValidationError not raised")

    def test_invalid_indoor_position(self):
        loc = self._create_location(type="indoor")
        ol = self._create_object_location(location=loc)
        ol.indoor = "TOTALLYWRONG"
        self._test_indoor_position_validation_error(ol)
        ol.indoor = "WRONG,WRONG"
        self._test_indoor_position_validation_error(ol)
        ol.indoor = "10,WRONG"
        self._test_indoor_position_validation_error(ol)
        ol.indoor = "WRONG,10"
        self._test_indoor_position_validation_error(ol)
        ol.indoor = "10,10.10,100"
        self._test_indoor_position_validation_error(ol)
        ol.indoor = "TOTALLY.WRONG"
        self._test_indoor_position_validation_error(ol)
        ol.indoor = "100.2300,-45.23454"
        ol.full_clean()
        # allow empty indoor for location whose indoor coordinates are not yet received
        ol.indoor = ""
        ol.full_clean()
        ol.save()
        ol.indoor = None
        ol.full_clean()
        ol.save()
        # outdoor allows empty but not invalid values
        loc.type = "outdoor"
        loc.full_clean()
        loc.save()
        ol.indoor = None
        ol.full_clean()
        ol.indoor = ""
        ol.full_clean()
        ol.indoor = "TOTALLY.WRONG"
        self._test_indoor_position_validation_error(ol)
        # outdoor does not allow valid indoor positions
        ol.indoor = "100.2300,-45.23454"
        self._test_indoor_position_validation_error(ol)

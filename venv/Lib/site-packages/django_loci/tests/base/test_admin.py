import json

import responses
from django.contrib.auth.models import Permission
from django.contrib.humanize.templatetags.humanize import ordinal
from django.urls import reverse

from .. import TestAdminMixin, TestLociMixin


class BaseTestAdmin(TestAdminMixin, TestLociMixin):
    app_label = "django_loci"
    geocode_url = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/"
    permission_model = Permission

    def test_location_list(self):
        self._login_as_admin()
        self._create_location(name="test-admin-location-1")
        url = reverse("{0}_location_changelist".format(self.url_prefix))
        r = self.client.get(url)
        self.assertContains(r, "test-admin-location-1")

    def test_floorplan_list(self):
        self._login_as_admin()
        self._create_floorplan()
        self._create_location()
        url = reverse("{0}_floorplan_changelist".format(self.url_prefix))
        r = self.client.get(url)
        self.assertContains(r, "1st floor")

    def test_location_json_view(self):
        self._login_as_admin()
        loc = self._create_location()
        r = self.client.get(reverse("admin:django_loci_location_json", args=[loc.pk]))
        expected = {
            "name": loc.name,
            "address": loc.address,
            "type": loc.type,
            "is_mobile": loc.is_mobile,
            "geometry": json.loads(loc.geometry.json),
        }
        self.assertDictEqual(r.json(), expected)

    def test_location_floorplan_json_view(self):
        self._login_as_admin()
        fl = self._create_floorplan()
        r = self.client.get(
            reverse("admin:django_loci_location_floorplans_json", args=[fl.location.pk])
        )
        expected = {
            "choices": [
                {
                    "id": str(fl.pk),
                    "str": str(fl),
                    "floor": fl.floor,
                    "image": fl.image.url,
                    "image_width": fl.image.width,
                    "image_height": fl.image.height,
                }
            ]
        }
        self.assertDictEqual(r.json(), expected)

    def test_location_change_image_removed(self):
        self._login_as_admin()
        loc = self._create_location(name="test-admin-location-1", type="indoor")
        fl = self._create_floorplan(location=loc)
        # remove floorplan image
        fl.image.delete(save=False)
        url = reverse("{0}_location_change".format(self.url_prefix), args=[loc.pk])
        r = self.client.get(url)
        self.assertContains(r, "test-admin-location-1")

    def test_floorplan_change_image_removed(self):
        self._login_as_admin()
        loc = self._create_location(name="test-admin-location-1", type="indoor")
        fl = self._create_floorplan(location=loc)
        # remove floorplan image
        fl.image.delete(save=False)
        url = reverse("{0}_floorplan_change".format(self.url_prefix), args=[fl.pk])
        r = self.client.get(url)
        self.assertContains(r, "test-admin-location-1")

    def test_floorplan_add_view_filters_indoor_location(self):
        self._login_as_admin()
        loc_indoor = self._create_location(
            name="test-admin-indoor-location", type="indoor"
        )
        loc_outdoor = self._create_location(
            name="test-admin-outdoor-location", type="outdoor"
        )
        url = reverse("{0}_floorplan_add".format(self.url_prefix))
        filter_url = (
            f"/admin/{self.app_label}/location/?_to_field=id&type__exact=indoor"
        )
        r1 = self.client.get(url)
        self.assertContains(
            r1,
            f"""
                <a href="{filter_url}"
                class="related-lookup" id="lookup_id_location" title="Lookup">
                    Select item
                </a>
            """,
            html=True,
        )
        # Ensure that when the user clicks on the
        # filter URL only indoor locations are displayed
        r2 = self.client.get(filter_url)
        self.assertContains(r2, f"{loc_indoor.name}</a>")
        self.assertNotContains(r2, f"{loc_outdoor.name}</a>")

    def test_is_mobile_location_json_view(self):
        self._login_as_admin()
        loc = self._create_location(is_mobile=True, geometry=None)
        response = self.client.get(
            reverse("admin:django_loci_location_json", args=[loc.pk])
        )
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(content["geometry"], None)
        loc1 = self._create_location(
            name="location2", address="loc2 add", type="outdoor"
        )
        response1 = self.client.get(
            reverse("admin:django_loci_location_json", args=[loc1.pk])
        )
        self.assertEqual(response1.status_code, 200)
        content1 = json.loads(response1.content)
        expected = {
            "name": "location2",
            "address": "loc2 add",
            "type": "outdoor",
            "is_mobile": False,
            "geometry": {"type": "Point", "coordinates": [12.512124, 41.898903]},
        }
        self.assertEqual(content1, expected)

    @responses.activate
    def test_geocode(self):
        self._login_as_admin()
        address = "Red Square"
        url = "{0}?address={1}".format(
            reverse("admin:django_loci_location_geocode_api"), address
        )
        # Mock HTTP request to the URL to work offline
        responses.add(
            responses.GET,
            f"{self.geocode_url}findAddressCandidates?singleLine=Red+Square&f=json&maxLocations=1",
            body=self._load_content("base/static/test-geocode.json"),
            content_type="application/json",
        )
        response = self.client.get(url)
        response_lat = round(response.json()["lat"])
        response_lng = round(response.json()["lng"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_lat, 56)
        self.assertEqual(response_lng, 38)

    def test_geocode_no_address(self):
        self._login_as_admin()
        url = reverse("admin:django_loci_location_geocode_api")
        response = self.client.get(url)
        expected = {"error": "Address parameter not defined"}
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), expected)

    @responses.activate
    def test_geocode_invalid_address(self):
        self._login_as_admin()
        invalid_address = "thisaddressisnotvalid123abc"
        url = "{0}?address={1}".format(
            reverse("admin:django_loci_location_geocode_api"), invalid_address
        )
        responses.add(
            responses.GET,
            f"{self.geocode_url}findAddressCandidates?singleLine=thisaddressisnotvalid123abc"
            "&f=json&maxLocations=1",
            body=self._load_content("base/static/test-geocode-invalid-address.json"),
            content_type="application/json",
        )
        response = self.client.get(url)
        expected = {"error": "Not found location with given name"}
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), expected)

    @responses.activate
    def test_reverse_geocode(self):
        self._login_as_admin()
        lat = 52
        lng = 21
        url = "{0}?lat={1}&lng={2}".format(
            reverse("admin:django_loci_location_reverse_geocode_api"), lat, lng
        )
        # Mock HTTP request to the URL to work offline
        responses.add(
            responses.GET,
            f"{self.geocode_url}reverseGeocode?location=21.0%2C52.0&f=json&outSR=4326",
            body=self._load_content("base/static/test-reverse-geocode.json"),
            content_type="application/json",
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "POL")

    @responses.activate
    def test_reverse_location_with_no_address(self):
        self._login_as_admin()
        lat = -30
        lng = -30
        url = "{0}?lat={1}&lng={2}".format(
            reverse("admin:django_loci_location_reverse_geocode_api"), lat, lng
        )
        responses.add(
            responses.GET,
            f"{self.geocode_url}reverseGeocode?location=-30.0%2C-30.0&f=json&outSR=4326",
            body=self._load_content(
                "base/static/test-reverse-location-with-no-address.json"
            ),
            content_type="application/json",
        )
        response = self.client.get(url)
        response_address = response.json()["address"]
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response_address, "")

    def test_reverse_geocode_no_coords(self):
        self._login_as_admin()
        url = reverse("admin:django_loci_location_reverse_geocode_api")
        response = self.client.get(url)
        expected = {"error": "lat or lng parameter not defined"}
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), expected)

    def _get_location_add_params(self, **kwargs):
        params = {
            "name": "test location",
            "type": "outdoor",
            "is_mobile": "",
            "address": "",
            "geometry": "",
            "floorplan_set-TOTAL_FORMS": "0",
            "floorplan_set-INITIAL_FORMS": "0",
            "floorplan_set-MIN_NUM_FORMS": "0",
            "floorplan_set-MAX_NUM_FORMS": "1000",
            "_save": "Save",
        }
        params.update(kwargs)
        return params

    def test_add_mobile_location(self):
        self._login_as_admin()
        url = reverse("{0}_location_add".format(self.url_prefix))
        params = self._get_location_add_params(is_mobile="on")
        response = self.client.post(url, params, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.location_model.objects.filter(is_mobile=True).count(), 1)

    def test_add_non_mobile_location_without_geometry(self):
        self._login_as_admin()
        url = reverse("{0}_location_add".format(self.url_prefix))
        params = self._get_location_add_params()
        response = self.client.post(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No geometry value provided.")
        self.assertEqual(self.location_model.objects.count(), 0)

    # for users with view only permissions to floorplans
    def test_readonly_floorplans(self):
        user = self._create_readonly_admin(models=[self.floorplan_model])
        self.client.force_login(user)
        loc = self._create_location(name="test-admin-location-1", type="indoor")
        fl = self._create_floorplan(location=loc)
        url = reverse("{0}_floorplan_change".format(self.url_prefix), args=[fl.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # assert if image is being rendered or not
        self.assertContains(r, 'img src="{0}"'.format(fl.image.url))
        self.assertContains(r, f"{loc.name} {ordinal(fl.floor)}")
        self.assertContains(r, fl.floor)
        self.assertContains(r, loc.name)

import json
import tempfile
from io import BytesIO
import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import TestCase
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from django.urls import reverse
from rest_framework.test import APITestCase
from django.utils.http import urlencode
from PIL import Image
from rest_framework.authtoken.models import Token
from swapper import load_model

from openwisp_controller.config.tests.utils import CreateConfigTemplateMixin
from openwisp_controller.geo.tests.test_admin import FloorPlan
from openwisp_controller.tests.utils import TestAdminMixin
from openwisp_users.tests.utils import TestOrganizationMixin
from openwisp_utils.tests import AssertNumQueriesSubTestMixin, capture_any_output

from .utils import TestGeoMixin

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')
OrganizationUser = load_model('openwisp_users', 'OrganizationUser')
Group = load_model('openwisp_users', 'Group')
User = get_user_model()


class TestApi(TestGeoMixin, TestCase):
    url_name = 'geo_api:device_coordinates'
    object_location_model = DeviceLocation
    location_model = Location
    object_model = Device

    def test_permission_404(self):
        url = reverse(self.url_name, args=[self.object_model().pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_permission_403(self):
        user = User.objects.create(
            username='tester',
            password='tester',
        )
        self.client.force_login(user)
        dl = self._create_object_location()
        url = reverse(self.url_name, args=[dl.device.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_method_not_allowed(self):
        device = self._create_object()
        url = reverse(self.url_name, args=[device.pk])
        r = self.client.post(url, {'key': device.key})
        self.assertEqual(r.status_code, 405)

    def test_get_existing_location(self):
        self.assertEqual(self.location_model.objects.count(), 0)
        dl = self._create_object_location()
        url = reverse(self.url_name, args=[dl.device.pk])
        self.assertEqual(self.location_model.objects.count(), 1)
        r = self.client.get(url, {'key': dl.device.key})
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(
            r.json(),
            {
                'type': 'Feature',
                'geometry': json.loads(dl.location.geometry.geojson),
                'properties': {'name': dl.location.name},
            },
        )
        self.assertEqual(self.location_model.objects.count(), 1)

    def test_get_existing_location_html(self):
        """
        Regression test for browsable web UI bug
        """
        dl = self._create_object_location()
        url = reverse(self.url_name, args=[dl.device.pk])
        r = self.client.get(url, {'key': dl.device.key}, HTTP_ACCEPT='text/html')
        self.assertEqual(r.status_code, 200)

    def test_get_create_location(self):
        self.assertEqual(self.location_model.objects.count(), 0)
        device = self._create_object()
        url = reverse(self.url_name, args=[device.pk])
        r = self.client.get(url, {'key': device.key})
        self.assertEqual(r.status_code, 404)

    def test_put_update_coordinates(self):
        self.assertEqual(self.location_model.objects.count(), 0)
        dl = self._create_object_location()
        url = reverse(self.url_name, args=[dl.device.pk])
        url = '{0}?key={1}'.format(url, dl.device.key)
        self.assertEqual(self.location_model.objects.count(), 1)
        coords = json.loads(Point(2, 23).geojson)
        feature = json.dumps({'type': 'Feature', 'geometry': coords})
        r = self.client.put(url, feature, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        print(r.data)
        self.assertDictEqual(
            r.json(),
            {
                'type': 'Feature',
                'geometry': coords,
                'properties': {'name': dl.location.name},
            },
        )
        self.assertEqual(self.location_model.objects.count(), 1)

    @capture_any_output()
    def test_bearer_authentication(self):
        user = User.objects.create(
            username='admin', password='password', is_staff=True, is_superuser=True
        )
        token = Token.objects.create(user=user).key
        device = self._create_object_location().device

        with self.subTest('Test DeviceLocationView'):
            response = self.client.get(
                reverse(self.url_name, args=[device.pk]),
                data={'key': device.key},
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test GeoJsonLocationListView'):
            response = self.client.get(
                reverse('geo_api:location_geojson'),
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test LocationDeviceList'):
            location = self._create_location(organization=device.organization)
            response = self.client.get(
                reverse('geo_api:location_device_list', args=[location.id]),
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)


class TestMultitenantApi(
    TestOrganizationMixin, TestGeoMixin, TestCase, CreateConfigTemplateMixin
):
    object_location_model = DeviceLocation
    location_model = Location
    object_model = Device

    def setUp(self):
        super().setUp()
        # create 2 orgs
        self._create_org(name='org_b', slug='org_b')
        org_a = self._create_org(name='org_a', slug='org_a')
        user = self._create_operator()
        admin_group = Group.objects.get(name='Administrator')
        admin_group.user_set.add(user)
        # create an operator for org_a
        ou = OrganizationUser.objects.create(user=user, organization=org_a)
        ou.is_admin = True
        ou.save()
        # create a superuser
        self._create_admin(is_superuser=True)

    def _create_device_location(self, **kwargs):
        options = dict()
        options.update(kwargs)
        device_location = self.object_location_model(**options)
        device_location.full_clean()
        device_location.save()
        return device_location

    @capture_any_output()
    def test_location_device_list(self):
        url = 'geo_api:location_device_list'
        # create 2 devices and 2 device location for each org
        device_a = self._create_device(organization=self._get_org('org_a'))
        device_b = self._create_device(organization=self._get_org('org_b'))
        location_a = self._create_location(organization=self._get_org('org_a'))
        location_b = self._create_location(organization=self._get_org('org_b'))
        self._create_device_location(content_object=device_a, location=location_a)
        self._create_device_location(content_object=device_b, location=location_b)

        with self.subTest('Test location device list for org operator'):
            self.client.login(username='operator', password='tester')
            r = self.client.get(reverse(url, args=[location_a.id]))
            self.assertContains(r, str(device_a.id))
            r = self.client.get(reverse(url, args=[location_b.id]))
            self.assertEqual(r.status_code, 404)

        with self.subTest('Test location device list for org superuser'):
            self.client.login(username='admin', password='tester')
            r = self.client.get(reverse(url, args=[location_a.id]))
            self.assertContains(r, str(device_a.id))
            r = self.client.get(reverse(url, args=[location_b.id]))
            self.assertContains(r, str(device_b.id))

        with self.subTest('Test location device list for unauthenticated user'):
            self.client.logout()
            r = self.client.get(reverse(url, args=[location_a.id]))
            self.assertEqual(r.status_code, 401)

    @capture_any_output()
    def test_geojson_list(self):
        url = 'geo_api:location_geojson'
        # create 2 devices and 2 device location for each org
        org_a = self._get_org('org_a')
        org_b = self._get_org('org_b')
        device_a = self._create_device(organization=org_a)
        device_b = self._create_device(organization=org_b)
        location_a = self._create_location(organization=org_a)
        location_b = self._create_location(organization=org_b)
        self._create_device_location(content_object=device_a, location=location_a)
        self._create_device_location(content_object=device_b, location=location_b)

        with self.subTest('Test geojson list for org operator'):
            self.client.login(username='operator', password='tester')
            r = self.client.get(reverse(url))
            self.assertContains(r, str(location_a.pk))
            self.assertNotContains(r, str(location_b.pk))

        with self.subTest('Test geojson list for superuser'):
            self.client.login(username='admin', password='tester')
            r = self.client.get(reverse(url))
            self.assertContains(r, str(location_a.pk))
            self.assertContains(r, str(location_b.pk))

        with self.subTest('Test filtering using organization slug'):
            self.client.login(username='admin', password='tester')
            response = self.client.get(
                reverse(url), data={'organization_slug': org_a.slug}
            )
            response_data = response.data
            self.assertEqual(response_data['count'], 1)
            self.assertEqual(
                response_data['features'][0]['properties']['organization'], org_a.id
            )

        with self.subTest('Test geojson list unauthenticated user'):
            self.client.logout()
            r = self.client.get(reverse(url))
            self.assertEqual(r.status_code, 401)


class TestGeoApi(
    AssertNumQueriesSubTestMixin,
    TestOrganizationMixin,
    TestGeoMixin,
    TestAdminMixin,
    TestCase,
    CreateConfigTemplateMixin,
):
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = DeviceLocation

    def setUp(self):
        admin = self._create_admin()
        self.client.force_login(admin)

    def _create_device_location(self, **kwargs):
        options = dict()
        options.update(kwargs)
        device_location = self.object_location_model(**options)
        device_location.full_clean()
        device_location.save()
        return device_location

    def _get_in_memory_upload_file(self):
        image = Image.new("RGB", (100, 100))
        with tempfile.NamedTemporaryFile(suffix=".png", mode="w+b") as tmp_file:
            image.save(tmp_file, format="png")
            tmp_file.seek(0)
            byio = BytesIO(tmp_file.read())
            inm_file = InMemoryUploadedFile(
                file=byio,
                field_name="avatar",
                name="testImage.png",
                content_type="image/png",
                size=byio.getbuffer().nbytes,
                charset=None,
            )
        return inm_file

    def test_create_devicelocation_using_related_ids(self):
        device = self._create_object()
        floorplan = self._create_floorplan()
        location = floorplan.location
        url = reverse('geo_api:device_location', args=[device.id])
        response = self.client.post(
            url,
            data={
                'location': location.id,
                'floorplan': floorplan.id,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['location']['id'], str(location.id))
        self.assertIn('type', response.data['location'].keys())
        self.assertIn('geometry', response.data['location'].keys())
        self.assertIn('properties', response.data['location'].keys())
        self.assertEqual(response.data['floorplan']['id'], str(floorplan.id))
        self.assertIn('name', response.data['floorplan'].keys())
        self.assertIn('floor', response.data['floorplan'].keys())
        self.assertIn('image', response.data['floorplan'].keys())
        # New location and floorplan objects are not created.
        self.assertEqual(self.location_model.objects.count(), 1)
        self.assertEqual(self.floorplan_model.objects.count(), 1)

    def test_create_devicelocation_location_floorplan(self):
        device = self._create_object()
        self.assertEqual(self.location_model.objects.count(), 0)
        self.assertEqual(self.object_location_model.objects.count(), 0)
        self.assertEqual(self.floorplan_model.objects.count(), 0)
        url = reverse('geo_api:device_location', args=[device.id])
        data = {
            'location.name': 'test-location',
            'location.address': 'Via del Corso, Roma, Italia',
            'location.geometry': 'SRID=4326;POINT (12.512124 41.898903)',
            'location.type': 'outdoor',
            'floorplan.floor': 1,
            'floorplan.image': self._get_in_memory_upload_file(),
        }
        response = self.client.post(
            url, data=data, format='multipart'
        )

        print(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.location_model.objects.count(), 1)
        self.assertEqual(self.object_location_model.objects.count(), 1)
        self.assertEqual(self.floorplan_model.objects.count(), 1)

    def test_get_floorplan_list(self):
        path = reverse('geo_api:list_floorplan')
        with self.assertNumQueries(3):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_filter_floorplan_list(self):
        f1 = self._create_floorplan(floor=10)
        org1 = self._create_org(name='org1')
        l1 = self._create_location(type='indoor', organization=org1)
        f2 = self._create_floorplan(floor=13, location=l1)
        staff_user = self._get_operator()
        change_perm = Permission.objects.filter(codename='change_floorplan')
        staff_user.user_permissions.add(*change_perm)
        self._create_org_user(user=staff_user, organization=org1, is_admin=True)
        self.client.force_login(staff_user)
        path = reverse('geo_api:list_floorplan')
        with self.assertNumQueries(6):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertContains(response, f2.id)
        self.assertNotContains(response, f1.id)

    def test_post_floorplan_list(self):
        l1 = self._create_location(type='indoor')
        path = reverse('geo_api:list_floorplan')
        temporary_image = tempfile.NamedTemporaryFile(suffix='.jpg')
        image = Image.new('RGB', (100, 100))
        image.save(temporary_image.name)
        data = {'floor': 1, 'image': temporary_image, 'location': l1.pk}
        with self.assertNumQueries(10):
            response = self.client.post(path, data, format='multipart')
        print(response.data)
        self.assertEqual(response.status_code, 201)

    def test_get_floorplan_detail(self):
        f1 = self._create_floorplan()
        path = reverse('geo_api:detail_floorplan', args=[f1.pk])
        with self.assertNumQueries(3):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_put_floorplan_detail(self):
        f1 = self._create_floorplan()
        l1 = self._create_location()
        path = reverse('geo_api:detail_floorplan', args=[f1.pk])
        temporary_image = tempfile.NamedTemporaryFile(suffix='.jpg')
        image = Image.new('RGB', (100, 100))
        image.save(temporary_image.name)
        data = {'floor': 12, 'image': temporary_image, 'location': l1.pk}
        with self.assertNumQueries(10):
            response = self.client.put(
                path, encode_multipart(BOUNDARY, data), content_type=MULTIPART_CONTENT
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['floor'], 12)
        self.assertEqual(response.data['location'], l1.pk)

    def test_patch_floorplan_detail(self):
        f1 = self._create_floorplan()
        self.assertEqual(f1.floor, 1)
        path = reverse('geo_api:detail_floorplan', args=[f1.pk])
        data = {'floor': 12}
        with self.assertNumQueries(8):
            response = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['floor'], 12)

    def test_delete_floorplan_detail(self):
        f1 = self._create_floorplan()
        path = reverse('geo_api:detail_floorplan', args=[f1.pk])
        with self.assertNumQueries(5):
            response = self.client.delete(path)
        self.assertEqual(response.status_code, 204)

    def test_get_location_list(self):
        path = reverse('geo_api:list_location')
        with self.assertNumQueries(3):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_filter_location_list(self):
        l1 = self._create_location(name='location-1')
        org1 = self._create_org(name='org1')
        l2 = self._create_location(type='indoor', organization=org1)
        staff_user = self._get_operator()
        change_perm = Permission.objects.filter(codename='change_location')
        staff_user.user_permissions.add(*change_perm)
        self._create_org_user(user=staff_user, organization=org1, is_admin=True)
        self.client.force_login(staff_user)
        path = reverse('geo_api:list_location')
        with self.assertNumQueries(7):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertContains(response, l2.id)
        self.assertNotContains(response, l1.id)

    def test_post_location_list(self):
        path = reverse('geo_api:list_location')
        coords = json.loads(Point(2, 23).geojson)
        data = {
            'organization': self._get_org().pk,
            'name': 'test-location',
            'type': 'outdoor',
            'is_mobile': False,
            'address': 'Via del Corso, Roma, Italia',
            'geometry': coords,
        }
        with self.assertNumQueries(9):
            response = self.client.post(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_get_location_detail(self):
        l1 = self._create_location()
        path = reverse('geo_api:detail_location', args=[l1.pk])
        with self.assertNumQueries(4):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_put_location_detail(self):
        l1 = self._create_location()
        path = reverse('geo_api:detail_location', args=[l1.pk])
        org1 = self._create_org(name='org1')
        coords = json.loads(Point(2, 23).geojson)
        data = {
            'organization': org1.pk,
            'name': 'change-test-location',
            'type': 'outdoor',
            'is_mobile': False,
            'address': 'Via del Corso, Roma, Italia',
            'geometry': coords,
        }
        with self.assertNumQueries(6):
            response = self.client.put(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['organization'], org1.pk)
        self.assertEqual(response.data['name'], 'change-test-location')

    def test_patch_location_detail(self):
        l1 = self._create_location()
        self.assertEqual(l1.name, 'test-location')
        path = reverse('geo_api:detail_location', args=[l1.pk])
        data = {'name': 'change-test-location'}
        with self.assertNumQueries(5):
            response = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'change-test-location')

    def test_create_location_outdoor_with_floorplan(self):
        path = reverse('geo_api:list_location')
        coords = json.loads(Point(2, 23).geojson)
        data = {
            'organization': self._get_org().pk,
            'name': 'test-location',
            'type': 'outdoor',
            'is_mobile': False,
            'address': 'Via del Corso, Roma, Italia',
            'geometry': coords,
            'floorplan': {'floor': 12},
        }
        with self.assertNumQueries(3):
            response = self.client.post(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Floorplan can only be added with location of the type indoor",
            str(response.content),
        )

    def test_patch_floorplan_detail_api(self):
        l1 = self._create_location(type='indoor')
        fl = self._create_floorplan(location=l1)
        path = reverse('geo_api:detail_location', args=[l1.pk])
        data = {'floorplan': {'floor': 13}}
        with self.assertNumQueries(13):
            response = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        fl.refresh_from_db()
        self.assertEqual(fl.floor, 13)

    def test_change_location_type_to_outdoor_api(self):
        l1 = self._create_location(type='indoor')
        self._create_floorplan(location=l1)
        path = reverse('geo_api:detail_location', args=[l1.pk])
        data = {'type': 'outdoor'}
        with self.assertNumQueries(8):
            response = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['floorplan'], [])

    def test_delete_location_detail(self):
        l1 = self._create_location()
        path = reverse('geo_api:detail_location', args=[l1.pk])
        with self.assertNumQueries(6):
            response = self.client.delete(path)
        self.assertEqual(response.status_code, 204)

    def test_device_location_with_outdoor_api(self):
        device = self._create_device()
        url = reverse('geo_api:device_location', args=[device.pk])
        path = '{0}?key={1}'.format(url, device.key)
        org1 = device.organization
        l1 = self._create_location(
            name='location1org', type='indoor', organization=org1
        )
        fl = self._create_floorplan(floor=13, location=l1)
        dl = self._create_device_location(
            content_object=device, floorplan=fl, location=l1, indoor="123.1, 32"
        )
        self.assertEqual(dl.floorplan, fl)
        data = {'location': {'type': 'Feature', 'properties': {'type': 'outdoor'}}}
        with self.assertNumQueries(5):
            response = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['location']['properties']['type'], 'outdoor')
        self.assertIsNone(response.data['floorplan'])
        dl.refresh_from_db()
        self.assertEqual(dl.location.type, 'outdoor')
        self.assertIsNone(dl.floorplan)

    def test_device_location_floorplan_update(self):
        device = self._create_device()
        url = reverse('geo_api:device_location', args=[device.pk])
        path = '{0}?key={1}'.format(url, device.key)
        org1 = device.organization
        l1 = self._create_location(
            name='location1org', type='indoor', organization=org1
        )
        fl = self._create_floorplan(floor=13, location=l1)
        self._create_device_location(
            content_object=device, floorplan=fl, location=l1, indoor="123.1, 32"
        )
        data = {'floorplan': {'floor': 31}}
        with self.assertNumQueries(11):
            response = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['floorplan']['floor'], 31)
        fl.refresh_from_db()
        self.assertEqual(fl.floor, 31)

    def test_patch_update_coordinates_of_device_api(self):
        device = self._create_device()
        url = reverse('geo_api:device_location', args=[device.pk])
        path = '{0}?key={1}'.format(url, device.key)
        org1 = device.organization
        l1 = self._create_location(
            name='location1org', type='outdoor', organization=org1
        )
        self._create_device_location(content_object=device, location=l1)
        self.assertEqual(l1.geometry.coords, (12.512124, 41.898903))
        data = {
            'location': {
                'geometry': {'type': 'Point', 'coordinates': [13.512124, 42.898903]}
            }
        }
        with self.assertNumQueries(5):
            response = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        l1.refresh_from_db()
        self.assertEqual(l1.geometry.coords, (13.512124, 42.898903))

    def test_put_to_change_full_location_detail_api(self):
        device = self._create_device()
        url = reverse('geo_api:device_location', args=[device.pk])
        path = '{0}?key={1}'.format(url, device.key)
        org1 = device.organization
        l1 = self._create_location(
            name='location1org', type='outdoor', organization=org1
        )
        self._create_device_location(content_object=device, location=l1)
        coords1 = l1.geometry.coords
        self.assertEqual(coords1, (12.512124, 41.898903))
        self.assertEqual(l1.name, 'location1org')
        self.assertEqual(l1.address, 'Via del Corso, Roma, Italia')
        data = {
            'location': {
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [13.51, 51.89]},
                'properties': {
                    'type': 'outdoor',
                    'is_mobile': False,
                    'name': 'GSoC21',
                    'address': 'Change Via del Corso, Roma, Italia',
                },
            }
        }
        with self.assertNumQueries(5):
            response = self.client.put(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        l1.refresh_from_db()
        self.assertNotEqual(coords1, l1.geometry.coords)
        self.assertEqual(l1.geometry.coords, (13.51, 51.89))
        self.assertEqual(l1.name, 'GSoC21')
        self.assertEqual(l1.address, 'Change Via del Corso, Roma, Italia')

    def test_create_location_with_floorplan(self):
        path = reverse('geo_api:list_location')
        fl_image = self._get_in_memory_upload_file()
        coords = json.loads(Point(2, 23).geojson)
        data = {
            'organization': self._get_org().pk,
            'name': 'GSoC21',
            'type': 'indoor',
            'is_mobile': False,
            'address': 'Via del Corso, Roma, Italia',
            'geometry': [coords],
            'floorplan.floor': ['23'],
            'floorplan.image': [fl_image],
        }
        with self.assertNumQueries(16):
            response = self.client.post(path, data, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Location.objects.count(), 1)
        self.assertEqual(FloorPlan.objects.count(), 1)

    def test_create_new_floorplan_with_put_location_api(self):
        org1 = self._get_org()
        l1 = self._create_location(
            name='location1org', type='outdoor', organization=org1
        )
        path = reverse('geo_api:detail_location', args=(l1.pk,))
        coords = json.loads(Point(2, 23).geojson)
        fl_image = self._get_in_memory_upload_file()
        data = {
            'organization': self._get_org().pk,
            'name': 'GSoC21',
            'type': 'indoor',
            'is_mobile': False,
            'address': 'Via del Corso, Roma, Italia',
            'geometry': [coords],
            'floorplan.floor': '23',
            'floorplan.image': fl_image,
        }
        with self.assertNumQueries(16):
            response = self.client.put(
                path, encode_multipart(BOUNDARY, data), content_type=MULTIPART_CONTENT
            )
        self.assertEqual(response.status_code, 200)

    def test_device_location_unauth_no_key(self):
        device = self._create_device()
        path = reverse('geo_api:device_location', args=(device.pk,))
        self.client.logout()
        with self.assertNumQueries(1):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 401)

    def test_device_location_auth_access_own_org_data_with_no_key(self):
        org1 = self._create_org(name='org1')
        device = self._create_device(name='00:12:23:34:45:56', organization=org1)
        staff_user = self._get_operator()
        device_perm = Permission.objects.filter(codename__endswith='device')
        staff_user.user_permissions.add(*device_perm)
        self._create_org_user(user=staff_user, organization=org1, is_admin=True)
        self.client.force_login(staff_user)
        path = reverse('geo_api:device_location', args=(device.pk,))
        l1 = self._create_location(
            name='location1org', type='outdoor', organization=org1
        )
        self._create_device_location(content_object=device, location=l1)
        with self.assertNumQueries(6):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_device_location_auth_access_different_org_data_with_no_key(self):
        org2 = self._create_org(name='org2')
        org1 = self._create_org(name='org1')
        device2 = self._create_device(name='00:11:22:33:44:66', organization=org2)
        staff_user = self._get_operator()
        device_perm = Permission.objects.filter(codename__endswith='device')
        staff_user.user_permissions.add(*device_perm)
        self._create_org_user(user=staff_user, organization=org1, is_admin=True)
        self.client.force_login(staff_user)
        path = reverse('geo_api:device_location', args=(device2.pk,))
        with self.assertNumQueries(5):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

    def test_device_location_auth_access_different_org_data_with_key(self):
        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org2')
        device2 = self._create_device(name='00:11:22:33:44:66', organization=org2)
        staff_user = self._get_operator()
        device_perm = Permission.objects.filter(codename__endswith='device')
        staff_user.user_permissions.add(*device_perm)
        self._create_org_user(user=staff_user, organization=org1, is_admin=True)
        self.client.force_login(staff_user)
        url = reverse('geo_api:device_location', args=(device2.pk,))
        path = '{0}?key={1}'.format(url, device2.key)
        l1 = self._create_location(
            name='location1org', type='outdoor', organization=org2
        )
        self._create_device_location(content_object=device2, location=l1)
        with self.assertNumQueries(3):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_device_location_unauth_with_correct_key(self):
        device = self._create_device()
        l1 = self._create_location(
            name='location1org', type='outdoor', organization=device.organization
        )
        self._create_device_location(content_object=device, location=l1)
        url = reverse('geo_api:device_location', args=(device.pk,))
        path = '{0}?key={1}'.format(url, device.key)
        self.client.logout()
        with self.assertNumQueries(1):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_device_location_unauth_with_wrong_key(self):
        device = self._create_device()
        url = reverse('geo_api:device_location', args=(device.pk,))
        path = '{0}?key={1}'.format(url, 12345)
        self.client.logout()
        with self.assertNumQueries(1):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 401)

    def test_update_device_location_to_indoor_api(self):
        org1 = self._create_org(name='org1')
        staff_user = self._get_operator()
        device_perm = Permission.objects.filter(codename__endswith='device')
        staff_user.user_permissions.add(*device_perm)
        self._create_org_user(user=staff_user, organization=org1, is_admin=True)
        self.client.force_login(staff_user)
        device = self._create_device(name='00:22:23:34:45:56', organization=org1)
        l1 = self._create_location(
            name='location1org', type='outdoor', organization=org1
        )
        self._create_device_location(content_object=device, location=l1)
        path = reverse('geo_api:device_location', args=[device.pk])
        coords = json.loads(Point(2, 23).geojson)
        fl_image = self._get_in_memory_upload_file()
        data = {
            'location.type': 'indoor',
            'location.name': 'GSoC21',
            'location.address': 'OpenWISP',
            'location.geometry': [coords],
            'floorplan.floor': ['21'],
            'indoor': ['12.342,23.541'],
            'floorplan.image': [fl_image],
        }
        with self.assertNumQueries(11):
            response = self.client.put(
                path, encode_multipart(BOUNDARY, data), content_type=MULTIPART_CONTENT
            )
        self.assertEqual(response.status_code, 200)

    def test_put_device_location_in_json_form(self):
        org1 = self._create_org(name='org1')
        staff_user = self._get_operator()
        device_perm = Permission.objects.filter(codename__endswith='device')
        staff_user.user_permissions.add(*device_perm)
        self._create_org_user(user=staff_user, organization=org1, is_admin=True)
        self.client.force_login(staff_user)
        device = self._create_device(name='00:22:23:34:45:56', organization=org1)
        l1 = self._create_location(
            name='location1org', type='indoor', organization=org1
        )
        fl = self._create_floorplan(floor=13, location=l1)
        self._create_device_location(
            content_object=device, floorplan=fl, location=l1, indoor="123.1, 32"
        )
        data = {
            'location': {
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [12.3456, 20.345]},
                'properties': {
                    'type': 'indoor',
                    'is_mobile': False,
                    'name': 'GSoC21',
                    'address': 'OpenWISP',
                },
            },
            'floorplan': {'floor': 37, 'image': 'http://url-of-the-image'},
            'indoor': '10.332,10.3223',
        }
        path = reverse('geo_api:device_location', args=[device.pk])
        with self.assertNumQueries(15):
            response = self.client.put(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def test_create_device_location_with_put_api(self):
        org1 = self._create_org(name='org1')
        staff_user = self._get_operator()
        device_perm = Permission.objects.filter(codename__endswith='device')
        staff_user.user_permissions.add(*device_perm)
        self._create_org_user(user=staff_user, organization=org1, is_admin=True)
        self.client.force_login(staff_user)
        device = self._create_device(name='00:22:23:34:45:56', organization=org1)
        path = reverse('geo_api:device_location', args=[device.pk])
        data = {
            'location': {
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [12.3456, 20.345]},
                'properties': {
                    'type': 'outdoor',
                    'is_mobile': False,
                    'name': 'GSoC21',
                    'address': 'OpenWISP',
                },
            },
        }
        self.assertEqual(DeviceLocation.objects.count(), 0)
        with self.assertNumQueries(16):
            response = self.client.put(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DeviceLocation.objects.count(), 1)

    def test_create_device_location_with_floorplan_with_put_api(self):
        org1 = self._create_org(name='org1')
        staff_user = self._get_operator()
        device_perm = Permission.objects.filter(codename__endswith='device')
        staff_user.user_permissions.add(*device_perm)
        self._create_org_user(user=staff_user, organization=org1, is_admin=True)
        self.client.force_login(staff_user)
        device = self._create_device(name='00:22:23:34:45:56', organization=org1)
        path = reverse('geo_api:device_location', args=[device.pk])
        coords = json.loads(Point(2, 23).geojson)
        fl_image = self._get_in_memory_upload_file()
        data = {
            'location.type': 'indoor',
            'location.name': 'GSoC21',
            'location.address': 'OpenWISP',
            'location.geometry': [coords],
            'floorplan.floor': ['21'],
            'indoor': ['12.342,23.541'],
            'floorplan.image': [fl_image],
        }
        self.assertEqual(DeviceLocation.objects.count(), 0)
        with self.assertNumQueries(19):
            response = self.client.put(
                path, encode_multipart(BOUNDARY, data), content_type=MULTIPART_CONTENT
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DeviceLocation.objects.count(), 1)

    def test_create_outdoor_device_location_with_floorplan_put_api(self):
        org1 = self._create_org(name='org1')
        staff_user = self._get_operator()
        device_perm = Permission.objects.filter(codename__endswith='device')
        staff_user.user_permissions.add(*device_perm)
        self._create_org_user(user=staff_user, organization=org1, is_admin=True)
        self.client.force_login(staff_user)
        device = self._create_device(name='00:22:23:34:45:56', organization=org1)
        path = reverse('geo_api:device_location', args=[device.pk])
        coords = json.loads(Point(2, 23).geojson)
        fl_image = self._get_in_memory_upload_file()
        data = {
            'location.type': 'outdoor',
            'location.name': 'GSoC21',
            'location.address': 'OpenWISP',
            'location.geometry': [coords],
            'floorplan.floor': ['21'],
            'indoor': ['12.342,23.541'],
            'floorplan.image': [fl_image],
        }
        self.assertEqual(DeviceLocation.objects.count(), 0)
        with self.assertNumQueries(16):
            response = self.client.put(
                path, encode_multipart(BOUNDARY, data), content_type=MULTIPART_CONTENT
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DeviceLocation.objects.count(), 1)

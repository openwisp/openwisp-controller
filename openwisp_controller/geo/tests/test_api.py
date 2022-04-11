import json
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from django.urls import reverse
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
        location = self._create_location(type='indoor')
        path = reverse('geo_api:list_floorplan')
        data = {'floor': 1, 'image': self._get_simpleuploadedfile(), 'location': location.pk}
        self.assertEqual(self.floorplan_model.objects.count(), 0)
        with self.assertNumQueries(10):
            response = self.client.post(path, data, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.floorplan_model.objects.count(), 1)
        self.assertEqual(response.data['organization'], location.organization_id)
        self.assertEqual(response.data['location'], location.id)

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

    def test_create_location_with_floorplan(self):
        path = reverse('geo_api:list_location')
        fl_image = self._get_simpleuploadedfile()
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
        fl_image = self._get_simpleuploadedfile()
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

    def test_create_devicelocation_outdoor_location_with_floorplan(self):
        device = self._create_object()
        path = reverse('geo_api:device_location', args=[device.pk])
        data = {
            'location.name': 'test-location',
            'location.address': 'Via del Corso, Roma, Italia',
            'location.geometry': 'SRID=4326;POINT (12.512124 41.898903)',
            'location.type': 'outdoor',
            'floorplan.floor': 1,
            'floorplan.image': self._get_simpleuploadedfile(),
        }
        self.assertEqual(self.object_location_model.objects.count(), 0)
        response = self.client.post(path, data, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            'floorplans can only be associated to locations of type "indoor"',
            response.data['floorplan']['__all__'][0],
        )
        self.assertEqual(self.object_location_model.objects.count(), 0)

    def test_create_devicelocation_using_related_ids(self):
        device = self._create_object()
        floorplan = self._create_floorplan()
        location = floorplan.location
        url = reverse('geo_api:device_location', args=[device.id])
        with self.assertNumQueries(6):
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
            'location.type': 'indoor',
            'floorplan.floor': 1,
            'floorplan.image': self._get_simpleuploadedfile(),
        }
        with self.assertNumQueries(20):
            response = self.client.post(url, data=data, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.location_model.objects.count(), 1)
        self.assertEqual(self.object_location_model.objects.count(), 1)
        self.assertEqual(self.floorplan_model.objects.count(), 1)

    def test_create_devicelocation_only_location(self):
        device = self._create_object()
        self.assertEqual(self.location_model.objects.count(), 0)
        self.assertEqual(self.object_location_model.objects.count(), 0)
        self.assertEqual(self.floorplan_model.objects.count(), 0)
        url = reverse('geo_api:device_location', args=[device.id])
        data = {
            'location': {
                'name': 'test-location',
                'address': 'Via del Corso, Roma, Italia',
                'geometry': 'SRID=4326;POINT (12.512124 41.898903)',
                'type': 'indoor',
            }
        }
        with self.assertNumQueries(10):
            response = self.client.post(url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.location_model.objects.count(), 1)
        self.assertEqual(self.object_location_model.objects.count(), 1)
        self.assertEqual(self.floorplan_model.objects.count(), 0)

    def test_create_devicelocation_only_floorplan(self):
        device = self._create_object()
        self.assertEqual(self.location_model.objects.count(), 0)
        self.assertEqual(self.object_location_model.objects.count(), 0)
        self.assertEqual(self.floorplan_model.objects.count(), 0)
        url = reverse('geo_api:device_location', args=[device.id])
        data = {
            'floorplan.floor': 1,
            'floorplan.image': self._get_simpleuploadedfile(),
        }
        with self.assertNumQueries(2):
            response = self.client.post(url, data=data, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertIn('This field is required.', response.data['location'][0])
        self.assertEqual(self.location_model.objects.count(), 0)
        self.assertEqual(self.object_location_model.objects.count(), 0)
        self.assertEqual(self.floorplan_model.objects.count(), 0)

    def test_create_devicelocation_existing_location_new_floorplan(self):
        device = self._create_object()
        location = self._create_location(type='indoor')
        self.assertEqual(self.location_model.objects.count(), 1)
        self.assertEqual(self.object_location_model.objects.count(), 0)
        self.assertEqual(self.floorplan_model.objects.count(), 0)
        url = reverse('geo_api:device_location', args=[device.id])
        data = {
            'location': str(location.id),
            'floorplan.floor': 1,
            'floorplan.image': self._get_simpleuploadedfile(),
        }
        with self.assertNumQueries(14):
            response = self.client.post(url, data=data, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.location_model.objects.count(), 1)
        self.assertEqual(self.object_location_model.objects.count(), 1)
        self.assertEqual(self.floorplan_model.objects.count(), 1)

    def test_update_devicelocation_change_location_outdoor_to_indoor(self):
        device_location = self._create_object_location()
        path = reverse('geo_api:device_location', args=[device_location.device.pk])
        data = {
            'location.type': 'indoor',
            'location.name': 'test-location',
            'location.address': 'Via del Corso, Roma, Italia',
            'location.geometry': 'SRID=4326;POINT (12.512124 41.898903)',
            'floorplan.floor': ['21'],
            'floorplan.image': self._get_simpleuploadedfile(),
            'indoor': ['12.342,23.541'],
        }
        self.assertEqual(device_location.location.type, 'outdoor')
        self.assertEqual(device_location.floorplan, None)
        with self.assertNumQueries(17):
            response = self.client.put(
                path, encode_multipart(BOUNDARY, data), content_type=MULTIPART_CONTENT
            )
        self.assertEqual(response.status_code, 200)
        device_location.refresh_from_db()
        self.assertEqual(device_location.location.type, 'indoor')
        self.assertNotEqual(device_location.floorplan, None)

    def test_update_devicelocation_patch_indoor(self):
        floorplan = self._create_floorplan()
        device_location = self._create_object_location(
            floorplan=floorplan, location=floorplan.location
        )
        path = reverse('geo_api:device_location', args=[device_location.device.pk])
        data = {
            'indoor': '0,0',
        }
        self.assertEqual(device_location.indoor, '-140.38620,40.369227')
        with self.assertNumQueries(4):
            response = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        device_location.refresh_from_db()
        self.assertEqual(device_location.indoor, '0,0')

    def test_update_devicelocation_floorplan_related_id(self):
        location = self._create_location(type='indoor')
        floor1 = self._create_floorplan(floor=1, location=location)
        floor2 = self._create_floorplan(floor=2, location=location)
        device_location = self._create_object_location(
            location=location, floorplan=floor1
        )
        path = reverse('geo_api:device_location', args=[device_location.device.pk])
        data = {
            'floorplan': str(floor2.id),
        }
        with self.assertNumQueries(6):
            response = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        device_location.refresh_from_db()
        self.assertEqual(device_location.floorplan, floor2)

    def test_update_devicelocation_location_related_id(self):
        location1 = self._create_location(name='test-location-1')
        location2 = self._create_location(name='test-location-2')
        device_location = self._create_object_location(location=location1)
        path = reverse('geo_api:device_location', args=[device_location.device.pk])
        data = {
            'location': str(location2.id),
        }
        with self.assertNumQueries(5):
            response = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        device_location.refresh_from_db()
        self.assertEqual(device_location.location, location2)

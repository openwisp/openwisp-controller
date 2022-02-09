import json

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from swapper import load_model

from openwisp_controller.config.tests.utils import CreateConfigTemplateMixin
from openwisp_users.tests.utils import TestOrganizationMixin
from openwisp_utils.tests import capture_any_output

from .utils import TestGeoMixin

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')
OrganizationUser = load_model('openwisp_users', 'OrganizationUser')
Group = load_model('openwisp_users', 'Group')
User = get_user_model()


class TestApi(TestGeoMixin, TestCase):
    url_name = 'geo_api:device_location'
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
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(
            r.json(),
            {'type': 'Feature', 'geometry': None, 'properties': {'name': device.name}},
        )
        self.assertEqual(self.location_model.objects.count(), 1)

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
        device = self._create_object()

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

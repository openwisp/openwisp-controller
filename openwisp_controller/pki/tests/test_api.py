from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_controller.tests.utils import TestAdminMixin
from openwisp_users.tests.utils import TestOrganizationMixin

from .utils import TestPkiMixin

Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')


class TestPkiApi(TestAdminMixin, TestPkiMixin, TestOrganizationMixin, TestCase):
    def setUp(self):
        super().setUp()
        self._login()

    _get_ca_data = {
        'name': 'Test CA',
        'organization': None,
        'key_length': '2048',
        'digest': 'sha256',
    }

    def test_ca_post_api(self):
        self.assertEqual(Ca.objects.count(), 0)
        path = reverse('controller_pki:api_ca_list')
        data = self._get_ca_data.copy()
        with self.assertNumQueries(4):
            r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Ca.objects.count(), 1)

    def test_ca_list_api(self):
        self._create_ca()
        path = reverse('controller_pki:api_ca_list')
        with self.assertNumQueries(4):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_ca_detail_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        path = reverse('controller_pki:api_ca_detail', args=[ca1.pk])
        with self.assertNumQueries(3):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], ca1.pk)

    def test_ca_put_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        path = reverse('controller_pki:api_ca_detail', args=[ca1.pk])
        org2 = self._create_org()
        data = {'name': 'change-ca1', 'organization': org2.pk, 'notes': 'change-notes'}
        with self.assertNumQueries(6):
            r = self.client.put(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'change-ca1')
        self.assertEqual(r.data['organization'], org2.pk)
        self.assertEqual(r.data['notes'], 'change-notes')

    def test_ca_patch_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        path = reverse('controller_pki:api_ca_detail', args=[ca1.pk])
        data = {
            'name': 'change-ca1',
        }
        with self.assertNumQueries(5):
            r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'change-ca1')

    def test_ca_download_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        path = reverse('controller_pki:api_ca_download', args=[ca1.pk])
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_ca_delete_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        path = reverse('controller_pki:api_ca_detail', args=[ca1.pk])
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Ca.objects.count(), 0)

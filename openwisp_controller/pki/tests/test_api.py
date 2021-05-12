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
        pass

    def test_ca_put_api(self):
        pass

    def test_ca_patch_api(self):
        pass

    def test_ca_download_api(self):
        pass

    def test_ca_delete_api(self):
        pass

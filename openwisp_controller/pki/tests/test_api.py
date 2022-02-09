from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_controller.tests.utils import TestAdminMixin
from openwisp_users.tests.test_api import AuthenticationMixin
from openwisp_users.tests.utils import TestOrganizationMixin
from openwisp_utils.tests import AssertNumQueriesSubTestMixin, capture_any_output

from .utils import TestPkiMixin

Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')


class TestPkiApi(
    AssertNumQueriesSubTestMixin,
    TestAdminMixin,
    TestPkiMixin,
    TestOrganizationMixin,
    AuthenticationMixin,
    TestCase,
):
    def setUp(self):
        super().setUp()
        self._login()

    _get_ca_data = {
        'name': 'Test CA',
        'organization': None,
        'key_length': '2048',
        'digest': 'sha256',
    }

    _get_cert_data = {
        'name': 'Test Cert',
        'organization': None,
        'ca': None,
        'key_length': '2048',
        'digest': 'sha256',
        'serial_number': "",
    }

    def test_ca_post_api(self):
        self.assertEqual(Ca.objects.count(), 0)
        path = reverse('pki_api:ca_list')
        data = self._get_ca_data.copy()
        with self.assertNumQueries(5):
            r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Ca.objects.count(), 1)

    def test_ca_post_with_extensions_field(self):
        self.assertEqual(Ca.objects.count(), 0)
        path = reverse('pki_api:ca_list')
        data = self._get_ca_data.copy()
        data['extensions'] = []
        with self.assertNumQueries(5):
            r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['extensions'], [])
        self.assertEqual(Ca.objects.count(), 1)

    def test_ca_import_post_api(self):
        ca1 = self._create_ca()
        path = reverse('pki_api:ca_list')
        data = {
            'name': 'import-ca-test',
            'organization': self._get_org().pk,
            'certificate': ca1.certificate,
            'private_key': ca1.private_key,
        }
        with self.assertNumQueries(6):
            r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Ca.objects.count(), 2)
        self.assertEqual(r.data['serial_number'], str(ca1.serial_number))
        self.assertEqual(r.data['state'], ca1.state)
        self.assertEqual(r.data['city'], ca1.city)
        self.assertEqual(r.data['email'], ca1.email)

    def test_ca_post_with_date_none_api(self):
        self.assertEqual(Ca.objects.count(), 0)
        path = reverse('pki_api:ca_list')
        data = {
            'name': 'test-ca',
            'organization': None,
            'validity_start': None,
            'validity_end': None,
        }
        with self.assertNumQueries(5):
            r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Ca.objects.count(), 1)

    def test_ca_list_api(self):
        self._create_ca()
        path = reverse('pki_api:ca_list')
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('passphrase', r.content.decode('utf8'))

    def test_ca_detail_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        path = reverse('pki_api:ca_detail', args=[ca1.pk])
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['id'], ca1.pk)
        self.assertEqual(r.data['extensions'], [])

    def test_ca_put_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        path = reverse('pki_api:ca_detail', args=[ca1.pk])
        org2 = self._create_org()
        data = {'name': 'change-ca1', 'organization': org2.pk, 'notes': 'change-notes'}
        with self.assertNumQueries(8):
            r = self.client.put(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'change-ca1')
        self.assertEqual(r.data['organization'], org2.pk)
        self.assertEqual(r.data['notes'], 'change-notes')

    def test_ca_patch_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        path = reverse('pki_api:ca_detail', args=[ca1.pk])
        data = {
            'name': 'change-ca1',
        }
        with self.assertNumQueries(7):
            r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'change-ca1')

    def test_crl_download_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        path = reverse('pki_api:crl_download', args=[ca1.pk])
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_ca_delete_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        path = reverse('pki_api:ca_detail', args=[ca1.pk])
        with self.assertNumQueries(6):
            r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Ca.objects.count(), 0)

    def test_ca_post_renew_api(self):
        ca1 = self._create_ca(name='ca1', organization=self._get_org())
        old_serial_num = ca1.serial_number
        path = reverse('pki_api:ca_renew', args=[ca1.pk])
        with self.assertNumQueries(5):
            r = self.client.post(path)
        ca1.refresh_from_db()
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(ca1.serial_number, old_serial_num)
        self.assertNotEqual(r.data['serial_number'], old_serial_num)

    def test_cert_post_api(self):
        path = reverse('pki_api:cert_list')
        data = self._get_cert_data.copy()
        data['ca'] = self._create_ca().pk
        with self.assertNumQueries(11):
            r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Cert.objects.count(), 1)

    def test_import_cert_post_api(self):
        path = reverse('pki_api:cert_list')
        ca1 = self._create_ca()
        data = {
            'name': 'import-test-ca',
            'organization': self._get_org().pk,
            'ca': ca1.id,
            'serial_number': '',
            'certificate': ca1.certificate,
            'private_key': ca1.private_key,
        }
        with self.assertNumQueries(10):
            r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Cert.objects.count(), 1)
        self.assertEqual(r.data['serial_number'], str(ca1.serial_number))
        self.assertEqual(r.data['state'], ca1.state)
        self.assertEqual(r.data['city'], ca1.city)
        self.assertEqual(r.data['email'], ca1.email)

    def test_cert_post_with_extensions_field(self):
        path = reverse('pki_api:cert_list')
        data = self._get_cert_data.copy()
        data['ca'] = self._create_ca().pk
        data['extensions'] = []
        with self.assertNumQueries(11):
            r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Cert.objects.count(), 1)
        self.assertEqual(r.data['extensions'], [])

    def test_cert_post_with_date_none(self):
        path = reverse('pki_api:cert_list')
        data = {
            'name': 'test-cert',
            'ca': self._create_ca().pk,
            'serial_number': "",
            'validity_start': None,
            'validity_end': None,
        }
        with self.assertNumQueries(11):
            r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Cert.objects.count(), 1)

    def test_cert_list_api(self):
        self._create_cert(name='cert1')
        path = reverse('pki_api:cert_list')
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Cert.objects.count(), 1)
        self.assertNotIn('passphrase', r.content.decode('utf8'))

    def test_cert_detail_api(self):
        cert1 = self._create_cert(name='cert1')
        path = reverse('pki_api:cert_detail', args=[cert1.pk])
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['id'], cert1.pk)
        self.assertEqual(r.data['extensions'], [])

    def test_cert_put_api(self):
        cert1 = self._create_cert(name='cert1')
        org2 = self._create_org()
        path = reverse('pki_api:cert_detail', args=[cert1.pk])
        data = {
            'name': 'cert1-change',
            'organization': org2.pk,
            'notes': 'new-notes',
        }
        with self.assertNumQueries(10):
            r = self.client.put(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'cert1-change')
        self.assertEqual(r.data['organization'], org2.pk)
        self.assertEqual(r.data['notes'], 'new-notes')

    def test_cert_patch_api(self):
        cert1 = self._create_cert(name='cert1')
        path = reverse('pki_api:cert_detail', args=[cert1.pk])
        data = {'name': 'cert1-change'}
        with self.assertNumQueries(9):
            r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'cert1-change')

    def test_cert_delete_api(self):
        cert1 = self._create_cert(name='cert1')
        path = reverse('pki_api:cert_detail', args=[cert1.pk])
        with self.assertNumQueries(7):
            r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Cert.objects.count(), 0)

    def test_ca_in_cert_detail_fields(self):
        cert1 = self._create_cert(name='cert1')
        path = reverse('pki_api:cert_detail', args=[cert1.pk])
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['ca'], cert1.ca.id)

    def test_post_cert_renew_api(self):
        cert1 = self._create_cert(name='cert1')
        old_serial_num = cert1.serial_number
        path = reverse('pki_api:cert_renew', args=[cert1.pk])
        with self.assertNumQueries(6):
            r = self.client.post(path)
        self.assertEqual(r.status_code, 200)
        cert1.refresh_from_db()
        self.assertNotEqual(cert1.serial_number, old_serial_num)
        self.assertNotEqual(r.data['serial_number'], old_serial_num)

    def test_post_cert_revoke_api(self):
        cert1 = self._create_cert(name='cert1')
        self.assertFalse(cert1.revoked)
        path = reverse('pki_api:cert_revoke', args=[cert1.pk])
        with self.assertNumQueries(6):
            r = self.client.post(path)
        cert1.refresh_from_db()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(cert1.revoked)
        self.assertTrue(r.data['revoked'])

    @capture_any_output()
    def test_bearer_authentication(self):
        self.client.logout()
        token = self._obtain_auth_token(username='admin', password='tester')
        ca = self._create_ca()
        cert = self._create_cert(ca=ca)
        with self.subTest('Test CaListCreateView'):
            response = self.client.get(
                reverse('pki_api:ca_list'),
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test CaDetailView'):
            response = self.client.get(
                reverse('pki_api:ca_detail', args=[ca.id]),
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test CaRenewView'):
            response = self.client.post(
                reverse('pki_api:ca_renew', args=[ca.id]),
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test CertListCreateView'):
            response = self.client.get(
                reverse('pki_api:cert_list'),
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test CertDetailView'):
            response = self.client.get(
                reverse('pki_api:cert_detail', args=[cert.id]),
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test CrlDownloadView'):
            response = self.client.get(
                reverse('pki_api:crl_download', args=[ca.id]),
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test CertRenewView'):
            response = self.client.post(
                reverse('pki_api:cert_renew', args=[cert.id]),
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test CertRevokeView'):
            response = self.client.post(
                reverse('pki_api:cert_revoke', args=[cert.id]),
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

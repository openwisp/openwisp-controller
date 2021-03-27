from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_controller.tests.utils import TestAdminMixin
from openwisp_users.tests.utils import TestOrganizationMixin

from .utils import CreateConfigTemplateMixin, TestVpnX509Mixin

Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')


class TestConfigApi(
    TestAdminMixin,
    TestOrganizationMixin,
    CreateConfigTemplateMixin,
    TestVpnX509Mixin,
    TestCase,
):
    def setUp(self):
        super().setUp()
        self._login()

    _get_template_data = {
        'name': 'test-template',
        'organization': None,
        'backend': 'netjsonconfig.OpenWrt',
        'config': {'interfaces': [{'name': 'eth0', 'type': 'ethernet'}]},
    }

    _get_vpn_data = {
        'name': 'vpn-test',
        'host': 'vpn.testing.com',
        'organization': None,
        'ca': None,
        'backend': 'openwisp_controller.vpn_backends.OpenVpn',
        'config': {
            'openvpn': [
                {
                    'ca': 'ca.pem',
                    'cert': 'cert.pem',
                    'dev': 'tap0',
                    'dev_type': 'tap',
                    'dh': 'dh.pem',
                    'key': 'key.pem',
                    'mode': 'server',
                    'name': 'example-vpn',
                    'proto': 'udp',
                    'tls_server': True,
                }
            ]
        },
    }

    _get_device_data = {
        'name': 'change-test-device',
        'organization': None,
        'mac_address': '00:11:22:33:44:55',
        'config': {
            'backend': 'netjsonconfig.OpenWrt',
            'status': 'modified',
            'templates': [],
            'context': '{}',
            'config': '{}',
        },
    }

    def test_device_create_api(self):
        self.assertEqual(Device.objects.count(), 0)
        path = reverse('configapi:device_list')
        data = self._get_device_data.copy()
        org = self._get_org()
        data['organization'] = org.pk
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Device.objects.count(), 1)

    def test_device_list_api(self):
        self._create_device()
        path = reverse('configapi:device_list')
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    # Device detail having no config
    def test_device_detail_api(self):
        d1 = self._create_device()
        path = reverse('configapi:device_detail', args=[d1.pk])
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['config'], None)

    # Device detail having config
    def test_device_detail_config_api(self):
        d1 = self._create_device()
        self._create_config(device=d1)
        path = reverse('configapi:device_detail', args=[d1.pk])
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.data['config'], None)

    def test_device_put_api(self):
        d1 = self._create_device(name="test-device")
        self._create_config(device=d1)
        path = reverse('configapi:device_detail', args=[d1.pk])
        org = self._get_org()
        data = {
            'name': 'change-test-device',
            'organization': org.pk,
            'mac_address': d1.mac_address,
            'config': {
                'backend': 'netjsonconfig.OpenWrt',
                'status': 'modified',
                'templates': [],
                'context': '{}',
                'config': '{}',
            },
        }

        r = self.client.put(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'change-test-device')
        self.assertEqual(r.data['organization'], org.pk)

    def test_device_patch_api(self):
        d1 = self._create_device(name="test-device")
        path = reverse('configapi:device_detail', args=[d1.pk])
        data = dict(name='change-test-device')
        r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'change-test-device')

    # Cannot remove/unasign Required templates
    def test_device_template_remove_api(self):
        d1 = self._create_device(name="test-device")
        c1 = self._create_config(device=d1)
        self.assertEqual(d1.config.templates.count(), 0)
        t1 = self._create_template(name='t1', required=True)
        c1.templates.add(t1.pk)
        data = {'config': {'templates': []}}
        path = reverse('configapi:device_detail', args=[d1.pk])
        r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertIn("Required templates cannot be Unassigned", str(r.content))
        self.assertEqual(d1.config.templates.count(), 1)

    def test_device_download_api(self):
        d1 = self._create_device()
        self._create_config(device=d1)
        path = reverse('configapi:download_device_config', args=[d1.pk])
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_device_delete_api(self):
        d1 = self._create_device()
        self._create_config(device=d1)
        path = reverse('configapi:device_detail', args=[d1.pk])
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Device.objects.count(), 0)

    def test_template_create_no_org_api(self):
        self.assertEqual(Template.objects.count(), 0)
        path = reverse('configapi:template_list')
        data = self._get_template_data.copy()
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(Template.objects.count(), 1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['organization'], None)

    def test_template_create_api(self):
        self.assertEqual(Template.objects.count(), 0)
        org = self._get_org()
        path = reverse('configapi:template_list')
        data = self._get_template_data.copy()
        data['organization'] = org.pk
        data['required'] = True
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(Template.objects.count(), 1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['organization'], org.pk)

    def test_template_list_api(self):
        org1 = self._get_org()
        self._create_template(name='t1', organization=org1)
        path = reverse('configapi:template_list')
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Template.objects.count(), 1)

    # template-detail having no Org
    def test_template_detail_api(self):
        t1 = self._create_template(name='t1')
        path = reverse('configapi:template_detail', args=[t1.pk])
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['organization'], None)

    def test_template_put_api(self):
        t1 = self._create_template(name='t1', organization=None)
        path = reverse('configapi:template_detail', args=[t1.pk])
        org = self._get_org()
        data = {
            'name': 'New t1',
            'required': True,
            'organization': org.pk,
            'backend': 'netjsonconfig.OpenWrt',
            'config': {'interfaces': [{'name': 'eth0', 'type': 'ethernet'}]},
        }
        r = self.client.put(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'New t1')
        self.assertEqual(r.data['organization'], org.pk)
        self.assertEqual(r.data['required'], True)

    def test_template_patch_api(self):
        t1 = self._create_template(name='t1')
        path = reverse('configapi:template_detail', args=[t1.pk])
        data = dict(name='New t1')
        r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'New t1')

    def test_template_download_api(self):
        t1 = self._create_template(name='t1')
        path = reverse('configapi:download_template_config', args=[t1.pk])
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_template_delete_api(self):
        t1 = self._create_template(name='t1')
        path = reverse('configapi:template_detail', args=[t1.pk])
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Template.objects.count(), 0)

    def test_vpn_create_api(self):
        self.assertEqual(Vpn.objects.count(), 0)
        path = reverse('configapi:vpn_list')
        ca1 = self._create_ca()
        data = self._get_vpn_data.copy()
        data['ca'] = ca1.pk
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Vpn.objects.count(), 1)

    def test_vpn_list_api(self):
        org = self._get_org()
        self._create_vpn(organization=org)
        path = reverse('configapi:vpn_list')
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    # VPN detail having no Org
    def test_vpn_detail_no_org_api(self):
        vpn1 = self._create_vpn(name='test-vpn')
        path = reverse('configapi:vpn_detail', args=[vpn1.pk])
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['organization'], None)

    # VPN detail having Org
    def test_vpn_detail_with_org_api(self):
        org = self._get_org()
        vpn1 = self._create_vpn(name='test-vpn', organization=org)
        path = reverse('configapi:vpn_detail', args=[vpn1.pk])
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['organization'], org.pk)

    def test_vpn_put_api(self):
        vpn1 = self._create_vpn(name='test-vpn')
        path = reverse('configapi:vpn_detail', args=[vpn1.pk])
        org = self._get_org()
        ca1 = self._create_ca()
        data = {
            'name': 'change-test-vpn',
            'host': 'vpn1.changetest.com',
            'organization': org.pk,
            'ca': ca1.pk,
            'backend': vpn1.backend,
            'config': vpn1.config,
        }
        r = self.client.put(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'change-test-vpn')
        self.assertEqual(r.data['ca'], ca1.pk)
        self.assertEqual(r.data['organization'], org.pk)

    def test_vpn_patch_api(self):
        vpn1 = self._create_vpn(name='test-vpn')
        path = reverse('configapi:vpn_detail', args=[vpn1.pk])
        data = dict(name='test-vpn-change')
        r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'test-vpn-change')

    def test_vpn_download_api(self):
        vpn1 = self._create_vpn(name='test-vpn')
        path = reverse('configapi:download_vpn_config', args=[vpn1.pk])
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_vpn_delete_api(self):
        vpn1 = self._create_vpn(name='test-vpn')
        path = reverse('configapi:vpn_detail', args=[vpn1.pk])
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Vpn.objects.count(), 0)

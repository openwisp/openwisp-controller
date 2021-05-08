from django.core.exceptions import ValidationError
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

    def test_device_create_with_config_api(self):
        self.assertEqual(Device.objects.count(), 0)
        path = reverse('controller_config:api_device_list')
        data = self._get_device_data.copy()
        org = self._get_org()
        data['organization'] = org.pk
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Device.objects.count(), 1)

    def test_device_create_no_config_api(self):
        self.assertEqual(Device.objects.count(), 0)
        path = reverse('controller_config:api_device_list')
        data = self._get_device_data.copy()
        org = self._get_org()
        data['organization'] = org.pk
        data.pop('config')
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Device.objects.count(), 1)

    def test_device_create_with_invalid_name_api(self):
        path = reverse('controller_config:api_device_list')
        data = self._get_device_data.copy()
        org = self._get_org()
        data.pop('config')
        data['name'] = 'T E S T'
        data['organization'] = org.pk
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Must be either a valid hostname or mac address.', str(r.content))

    # POST request should fail with validation error
    def test_device_post_with_templates_of_different_org(self):
        path = reverse('controller_config:api_device_list')
        data = self._get_device_data.copy()
        org_1 = self._get_org()
        data['organization'] = org_1.pk
        org_2 = self._create_org(name='test org2', slug='test-org2')
        t1 = self._create_template(name='t1', organization=org_2)
        data['config']['templates'] += [str(t1.pk)]
        with self.assertRaises(ValidationError) as error:
            self.client.post(path, data, content_type='application/json')
        validation_msg = '''
                            The following templates are owned by
                            organizations which do not match the
                            organization of this configuration: t1
                        '''
        self.assertTrue(' '.join(validation_msg.split()) in error.exception.message)

    def test_device_list_api(self):
        self._create_device()
        path = reverse('controller_config:api_device_list')
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_device_filter_templates(self):
        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org2')
        test_user = self._create_operator(organizations=[org1])
        self.client.force_login(test_user)
        self._create_template(name='t0', organization=None)
        self._create_template(name='t1', organization=org1)
        self._create_template(name='t11', organization=org1)
        self._create_template(name='t2', organization=org2)
        path = reverse('controller_config:api_device_list')
        r = self.client.get(path, {'format': 'api'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 't0</option>')
        self.assertContains(r, 't1</option>')
        self.assertContains(r, 't11</option>')
        self.assertNotContains(r, 't2</option>')

    # Device detail having no config
    def test_device_detail_api(self):
        d1 = self._create_device()
        path = reverse('controller_config:api_device_detail', args=[d1.pk])
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['config'], None)

    # Device detail having config
    def test_device_detail_config_api(self):
        d1 = self._create_device()
        self._create_config(device=d1)
        path = reverse('controller_config:api_device_detail', args=[d1.pk])
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.data['config'], None)

    def test_device_put_api(self):
        d1 = self._create_device(name='test-device')
        self._create_config(device=d1)
        path = reverse('controller_config:api_device_detail', args=[d1.pk])
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

    # test device with VPN-client type template assigned to it
    def test_device_with_vpn_client_template_assigned(self):
        org1 = self._create_org(name='testorg')
        v1 = self._create_vpn(name='vpn1org', organization=org1)
        t1 = self._create_template(name='t1', organization=org1, type='vpn', vpn=v1)
        t2 = self._create_template(name='t2', organization=org1)
        d1 = self._create_device(name='d1', organization=org1)
        self._create_config(device=d1)
        path = reverse('controller_config:api_device_detail', args=[d1.pk])
        self.assertEqual(d1.config.vpnclient_set.count(), 0)
        data = {'config': {'templates': [str(t1.id), str(t2.id)]}}
        self.client.patch(path, data, content_type='application/json')
        self.assertEqual(d1.config.vpnclient_set.count(), 1)
        data1 = {'config': {'templates': []}}
        self.client.patch(path, data1, content_type='application/json')
        self.assertEqual(d1.config.vpnclient_set.count(), 0)

    def test_device_patch_with_templates_of_same_org(self):
        org1 = self._create_org(name='testorg')
        d1 = self._create_device(name='org1-config', organization=org1)
        self._create_config(device=d1)
        self.assertEqual(d1.config.templates.count(), 0)
        path = reverse('controller_config:api_device_detail', args=[d1.pk])
        t1 = self._create_template(name='t1', organization=None)
        t2 = self._create_template(name='t2', organization=org1)
        data = {'config': {'templates': [str(t1.id), str(t2.id)]}}
        r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d1.config.templates.count(), 2)
        self.assertEqual(r.data['config']['templates'], [t1.id, t2.id])

    def test_device_patch_with_templates_of_different_org(self):
        org1 = self._create_org(name='testorg')
        d1 = self._create_device(name='org1-config', organization=org1)
        self._create_config(device=d1)
        self.assertEqual(d1.config.templates.count(), 0)
        path = reverse('controller_config:api_device_detail', args=[d1.pk])
        t1 = self._create_template(name='t1', organization=None)
        t2 = self._create_template(name='t2', organization=org1)
        t3 = self._create_template(
            name='t3', organization=self._create_org(name='org2')
        )
        data = {'config': {'templates': [str(t1.id), str(t2.id), str(t3.id)]}}
        with self.assertRaises(ValidationError) as error:
            self.client.patch(path, data, content_type='application/json')
        validation_msg = '''
                            The following templates are owned by
                            organizations which do not match the
                            organization of this configuration: t3
                        '''
        self.assertTrue(' '.join(validation_msg.split()) in error.exception.message)

    def test_device_patch_api(self):
        d1 = self._create_device(name='test-device')
        path = reverse('controller_config:api_device_detail', args=[d1.pk])
        data = dict(name='change-test-device')
        r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'change-test-device')

    def test_device_download_api(self):
        d1 = self._create_device()
        self._create_config(device=d1)
        path = reverse('controller_config:api_download_device_config', args=[d1.pk])
        with self.assertNumQueries(6):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_device_delete_api(self):
        d1 = self._create_device()
        self._create_config(device=d1)
        path = reverse('controller_config:api_device_detail', args=[d1.pk])
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Device.objects.count(), 0)

    def test_template_create_no_org_api(self):
        self.assertEqual(Template.objects.count(), 0)
        path = reverse('controller_config:api_template_list')
        data = self._get_template_data.copy()
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(Template.objects.count(), 1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['organization'], None)

    def test_template_create_vpn_with_type_as_generic(self):
        path = reverse('controller_config:api_template_list')
        test_user = self._create_operator(organizations=[self._get_org()])
        self.client.force_login(test_user)
        vpn1 = self._create_vpn(name='vpn1', organization=self._get_org())
        data = self._get_template_data.copy()
        data['organization'] = self._get_org().pk
        data['type'] = 'generic'
        data['vpn'] = vpn1.id
        r = self.client.post(path, data, content_type='application/json')
        validation_msg = "To select a VPN, set the template type to 'VPN-client'"
        self.assertIn(validation_msg, r.data['vpn'])
        self.assertEqual(r.status_code, 400)

    def test_template_create_api(self):
        self.assertEqual(Template.objects.count(), 0)
        org = self._get_org()
        path = reverse('controller_config:api_template_list')
        data = self._get_template_data.copy()
        data['organization'] = org.pk
        data['required'] = True
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(Template.objects.count(), 1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['organization'], org.pk)

    def test_template_create_of_vpn_type(self):
        org = self._get_org()
        vpn1 = self._create_vpn(name='vpn1', organization=org)
        path = reverse('controller_config:api_template_list')
        data = self._get_template_data.copy()
        data['type'] = 'vpn'
        data['vpn'] = vpn1.id
        data['organization'] = org.pk
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(Template.objects.count(), 1)
        self.assertEqual(r.status_code, 201)

    def test_template_create_with_shared_vpn(self):
        org1 = self._get_org()
        test_user = self._create_operator(organizations=[org1])
        self.client.force_login(test_user)
        vpn1 = self._create_vpn(name='vpn1', organization=None)
        path = reverse('controller_config:api_template_list')
        data = self._get_template_data.copy()
        data['type'] = 'vpn'
        data['vpn'] = vpn1.id
        data['organization'] = org1.pk
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Template.objects.count(), 1)
        self.assertEqual(r.data['vpn'], vpn1.id)

    def test_template_creation_with_no_org_by_operator(self):
        path = reverse('controller_config:api_template_list')
        data = self._get_template_data.copy()
        test_user = self._create_operator(organizations=[self._get_org()])
        self.client.force_login(test_user)
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('This field may not be null.', str(r.content))

    def test_template_list_api(self):
        org1 = self._get_org()
        self._create_template(name='t1', organization=org1)
        path = reverse('controller_config:api_template_list')
        with self.assertNumQueries(5):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Template.objects.count(), 1)

    def test_template_list_for_shared_objects(self):
        org1 = self._get_org()
        self._create_vpn(name='shared-vpn', organization=None)
        test_user = self._create_operator(organizations=[org1])
        self.client.force_login(test_user)
        path = reverse('controller_config:api_template_list')
        r = self.client.get(path, {'format': 'api'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'shared-vpn</option>')

    # template-detail having no Org
    def test_template_detail_api(self):
        t1 = self._create_template(name='t1')
        path = reverse('controller_config:api_template_detail', args=[t1.pk])
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['organization'], None)

    def test_template_put_api(self):
        t1 = self._create_template(name='t1', organization=None)
        path = reverse('controller_config:api_template_detail', args=[t1.pk])
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
        path = reverse('controller_config:api_template_detail', args=[t1.pk])
        data = dict(name='New t1')
        r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'New t1')

    def test_template_download_api(self):
        t1 = self._create_template(name='t1')
        path = reverse('controller_config:api_download_template_config', args=[t1.pk])
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_template_delete_api(self):
        t1 = self._create_template(name='t1')
        path = reverse('controller_config:api_template_detail', args=[t1.pk])
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Template.objects.count(), 0)

    def test_vpn_create_api(self):
        self.assertEqual(Vpn.objects.count(), 0)
        path = reverse('controller_config:api_vpn_list')
        ca1 = self._create_ca()
        data = self._get_vpn_data.copy()
        data['ca'] = ca1.pk
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Vpn.objects.count(), 1)

    def test_vpn_create_with_shared_objects(self):
        org1 = self._get_org()
        shared_ca = self._create_ca(name='shared_ca', organization=None)
        test_user = self._create_operator(organizations=[org1])
        self.client.force_login(test_user)
        data = self._get_vpn_data.copy()
        data['organization'] = org1.pk
        data['ca'] = shared_ca.pk
        path = reverse('controller_config:api_vpn_list')
        r = self.client.post(path, data, content_type='application/json')
        self.assertEqual(Vpn.objects.count(), 1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['ca'], shared_ca.pk)

    def test_vpn_list_api(self):
        org = self._get_org()
        self._create_vpn(organization=org)
        path = reverse('controller_config:api_vpn_list')
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_vpn_list_for_shared_objects(self):
        self._create_ca(name='shared_ca', organization=None)
        self._create_cert(name='shared_cert', organization=None)
        org1 = self._get_org()
        test_user = self._create_operator(organizations=[org1])
        self.client.force_login(test_user)
        path = reverse('controller_config:api_vpn_list')
        r = self.client.get(path, {'format': 'api'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'shared_ca</option>')
        self.assertContains(r, 'shared_cert</option>')

    # VPN detail having no Org
    def test_vpn_detail_no_org_api(self):
        vpn1 = self._create_vpn(name='test-vpn')
        path = reverse('controller_config:api_vpn_detail', args=[vpn1.pk])
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['organization'], None)

    # VPN detail having Org
    def test_vpn_detail_with_org_api(self):
        org = self._get_org()
        vpn1 = self._create_vpn(name='test-vpn', organization=org)
        path = reverse('controller_config:api_vpn_detail', args=[vpn1.pk])
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['organization'], org.pk)

    def test_vpn_put_api(self):
        vpn1 = self._create_vpn(name='test-vpn')
        path = reverse('controller_config:api_vpn_detail', args=[vpn1.pk])
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
        path = reverse('controller_config:api_vpn_detail', args=[vpn1.pk])
        data = dict(name='test-vpn-change')
        r = self.client.patch(path, data, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'test-vpn-change')

    def test_vpn_download_api(self):
        vpn1 = self._create_vpn(name='test-vpn')
        path = reverse('controller_config:api_download_vpn_config', args=[vpn1.pk])
        with self.assertNumQueries(5):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_vpn_delete_api(self):
        vpn1 = self._create_vpn(name='test-vpn')
        path = reverse('controller_config:api_vpn_detail', args=[vpn1.pk])
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Vpn.objects.count(), 0)

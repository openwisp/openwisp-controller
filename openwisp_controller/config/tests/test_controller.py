from unittest import mock

from django.test import TestCase
from django.urls import reverse

from openwisp_users.tests.utils import TestOrganizationMixin

from ..models import Config, Device, OrganizationConfigSettings, Template
from . import CreateConfigTemplateMixin

TEST_MACADDR = '00:11:22:33:44:55'
TEST_MACADDR_NAME = TEST_MACADDR.replace(':', '-')
TEST_ORG_SHARED_SECRET = 'functional_testing_secret'
REGISTER_URL = reverse('controller:device_register')


class TestController(CreateConfigTemplateMixin, TestOrganizationMixin, TestCase):
    """
    tests for django_netjsonconfig.controller
    """

    config_model = Config
    device_model = Device
    template_model = Template

    def _create_org(self, shared_secret=TEST_ORG_SHARED_SECRET, **kwargs):
        org = super()._create_org(**kwargs)
        OrganizationConfigSettings.objects.create(
            organization=org, shared_secret=shared_secret
        )
        return org

    def test_register(self, **kwargs):
        org = self._create_org()
        response = self.client.post(
            REGISTER_URL,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertEqual(response.status_code, 201)
        count = Device.objects.filter(
            mac_address=TEST_MACADDR, organization=org
        ).count()
        self.assertEqual(count, 1)

    def test_register_template_tags(self):
        org1 = self._create_org(name='org1')
        t1 = self._create_template(name='t1', organization=org1)
        t1.tags.add('mesh')
        t_shared = self._create_template(name='t-shared')
        t_shared.tags.add('mesh')
        org2 = self._create_org(name='org2', shared_secret='org2secret')
        t2 = self._create_template(name='mesh', organization=org2)
        t2.tags.add('mesh')
        response = self.client.post(
            REGISTER_URL,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
                'tags': 'mesh',
            },
        )
        self.assertEqual(response.status_code, 201)
        d = Device.objects.filter(mac_address=TEST_MACADDR, organization=org1).first()
        self.assertEqual(d.config.templates.filter(name=t1.name).count(), 1)
        self.assertEqual(d.config.templates.filter(name=t_shared.name).count(), 1)

    def test_register_400(self):
        self._create_org()
        # missing secret
        response = self.client.post(
            REGISTER_URL,
            {
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertContains(response, 'secret', status_code=400)

    def test_register_403(self):
        self._create_org()
        # wrong secret
        response = self.client.post(
            REGISTER_URL,
            {
                'secret': 'WRONG',
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertContains(response, 'error: unrecognized secret', status_code=403)

    def test_register_403_disabled_registration(self):
        org = self._create_org()
        org.config_settings.registration_enabled = False
        org.config_settings.save()
        response = self.client.post(
            REGISTER_URL,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertContains(response, 'error: registration disabled', status_code=403)
        count = Device.objects.filter(
            mac_address=TEST_MACADDR, organization=org
        ).count()
        self.assertEqual(count, 0)

    def test_register_403_disabled_org(self):
        self._create_org(is_active=False)
        response = self.client.post(
            REGISTER_URL,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertContains(response, 'error: unrecognized secret', status_code=403)

    def test_checksum_404_disabled_org(self):
        org = self._create_org(is_active=False)
        c = self._create_config(organization=org)
        response = self.client.get(
            reverse('controller:device_checksum', args=[c.device.pk]),
            {'key': c.device.key},
        )
        self.assertEqual(response.status_code, 404)

    def test_download_config_404_disabled_org(self):
        org = self._create_org(is_active=False)
        c = self._create_config(organization=org)
        url = reverse('controller:device_download_config', args=[c.device.pk])
        response = self.client.get(url, {'key': c.device.key})
        self.assertEqual(response.status_code, 404)

    def test_report_status_404_disabled_org(self):
        org = self._create_org(is_active=False)
        c = self._create_config(organization=org)
        response = self.client.post(
            reverse('controller:device_report_status', args=[c.device.pk]),
            {'key': c.device.key, 'status': 'applied'},
        )
        self.assertEqual(response.status_code, 404)

    def test_checksum_200(self):
        org = self._create_org()
        c = self._create_config(organization=org)
        response = self.client.get(
            reverse('controller:device_checksum', args=[c.device.pk]),
            {'key': c.device.key},
        )
        self.assertEqual(response.status_code, 200)

    @mock.patch('django_netjsonconfig.settings.REGISTRATION_ENABLED', False)
    def test_register_403_disabled_registration_setting(self):
        org = self._create_org()
        response = self.client.post(
            REGISTER_URL,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertEqual(response.status_code, 403)
        count = Device.objects.filter(
            mac_address=TEST_MACADDR, organization=org
        ).count()
        self.assertEqual(count, 0)

    def test_ip_fields_not_duplicated(self):
        org1 = self._create_org()
        c1 = self._create_config(organization=org1)
        d2 = self._create_device(
            organization=org1, name='testdup', mac_address='00:11:22:33:66:77'
        )
        c2 = self._create_config(device=d2)
        org2 = self._create_org(shared_secret='123456')
        c3 = self._create_config(organization=org2)
        self.client.get(
            reverse('controller:device_checksum', args=[c3.device.pk]),
            {'key': c3.device.key, 'management_ip': '192.168.1.99'},
        )
        self.client.get(
            reverse('controller:device_checksum', args=[c1.device.pk]),
            {'key': c1.device.key, 'management_ip': '192.168.1.99'},
        )
        self.client.get(
            reverse('controller:device_checksum', args=[c2.device.pk]),
            {'key': c2.device.key, 'management_ip': '192.168.1.99'},
        )
        c1.refresh_from_db()
        c2.refresh_from_db()
        c3.refresh_from_db()
        # device previously having the IP now won't have it anymore
        self.assertNotEqual(c1.device.last_ip, c2.device.last_ip)
        self.assertNotEqual(c1.device.management_ip, c2.device.management_ip)
        # other organization is not affected
        self.assertEquals(c3.device.last_ip, '127.0.0.1')
        self.assertEqual(c3.device.management_ip, '192.168.1.99')

    # simulate public IP by mocking the
    # method which tells us if the ip is private or not
    @mock.patch('ipaddress.IPv4Address.is_private', False)
    def test_last_ip_public_can_be_duplicated(self):
        org1 = self._create_org()
        d1 = self._create_device(
            organization=org1, name='testdup1', mac_address='00:11:22:33:66:11'
        )
        c1 = self._create_config(device=d1)
        d2 = self._create_device(
            organization=org1, name='testdup2', mac_address='00:11:22:33:66:22'
        )
        c2 = self._create_config(device=d2)
        self.client.get(
            reverse('controller:device_checksum', args=[c1.device.pk]),
            {'key': c1.device.key, 'management_ip': '192.168.1.99'},
        )
        self.client.get(
            reverse('controller:device_checksum', args=[c2.device.pk]),
            {'key': c2.device.key, 'management_ip': '192.168.1.99'},
        )
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertEqual(c1.device.last_ip, c2.device.last_ip)
        self.assertNotEqual(c1.device.management_ip, c2.device.management_ip)

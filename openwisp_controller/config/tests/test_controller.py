from django.test import TestCase
from django.urls import reverse

from django_netjsonconfig import settings as django_netjsonconfig_settings
from openwisp_users.tests.utils import TestOrganizationMixin

from . import CreateConfigTemplateMixin
from ..models import Config, OrganizationConfigSettings

TEST_MACADDR = '00:11:22:33:44:55'
TEST_MACADDR_NAME = TEST_MACADDR.replace(':', '-')
TEST_ORG_SHARED_SECRET = 'functional_testing_secret'
REGISTER_URL = reverse('controller:register')


class TestController(CreateConfigTemplateMixin, TestOrganizationMixin,
                     TestCase):
    """
    tests for django_netjsonconfig.controller
    """
    config_model = Config

    def _create_org(self, **kwargs):
        org = super(TestController, self)._create_org(**kwargs)
        OrganizationConfigSettings.objects.create(organization=org,
                                                  shared_secret=TEST_ORG_SHARED_SECRET)
        return org

    def test_register(self):
        org = self._create_org()
        response = self.client.post(REGISTER_URL, {
            'secret': TEST_ORG_SHARED_SECRET,
            'name': TEST_MACADDR_NAME,
            'mac_address': TEST_MACADDR,
            'backend': 'netjsonconfig.OpenWrt'
        })
        self.assertEqual(response.status_code, 201)
        count = Config.objects.filter(mac_address=TEST_MACADDR,
                                      organization=org).count()
        self.assertEqual(count, 1)

    def test_register_400(self):
        self._create_org()
        # missing secret
        response = self.client.post(REGISTER_URL, {
            'name': TEST_MACADDR_NAME,
            'mac_address': TEST_MACADDR,
            'backend': 'netjsonconfig.OpenWrt'
        })
        self.assertContains(response, 'secret', status_code=400)

    def test_register_403(self):
        self._create_org()
        # wrong secret
        response = self.client.post(REGISTER_URL, {
            'secret': 'WRONG',
            'name': TEST_MACADDR_NAME,
            'mac_address': TEST_MACADDR,
            'backend': 'netjsonconfig.OpenWrt'
        })
        self.assertContains(response, 'unrecognized secret', status_code=403)

    def test_register_403_disabled_registration(self):
        org = self._create_org()
        org.config_settings.registration_enabled = False
        org.config_settings.save()
        response = self.client.post(REGISTER_URL, {
            'secret': TEST_ORG_SHARED_SECRET,
            'name': TEST_MACADDR_NAME,
            'mac_address': TEST_MACADDR,
            'backend': 'netjsonconfig.OpenWrt'
        })
        self.assertContains(response, 'registration disabled', status_code=403)
        count = Config.objects.filter(mac_address=TEST_MACADDR,
                                      organization=org).count()
        self.assertEqual(count, 0)

    def test_register_403_disabled_org(self):
        self._create_org(is_active=False)
        response = self.client.post(REGISTER_URL, {
            'secret': TEST_ORG_SHARED_SECRET,
            'name': TEST_MACADDR_NAME,
            'mac_address': TEST_MACADDR,
            'backend': 'netjsonconfig.OpenWrt'
        })
        self.assertContains(response, 'unrecognized secret', status_code=403)

    def test_checksum_404_disabled_org(self):
        org = self._create_org(is_active=False)
        c = self._create_config(organization=org)
        response = self.client.get(reverse('controller:checksum', args=[c.pk]), {'key': c.key})
        self.assertEqual(response.status_code, 404)

    def test_download_config_404_disabled_org(self):
        org = self._create_org(is_active=False)
        c = self._create_config(organization=org)
        response = self.client.get(reverse('controller:download_config', args=[c.pk]), {'key': c.key})
        self.assertEqual(response.status_code, 404)

    def test_report_status_404_disabled_org(self):
        org = self._create_org(is_active=False)
        c = self._create_config(organization=org)
        response = self.client.post(reverse('controller:report_status', args=[c.pk]),
                                    {'key': c.key, 'status': 'running'})
        self.assertEqual(response.status_code, 404)

    def test_checksum_200(self):
        org = self._create_org()
        c = self._create_config(organization=org)
        response = self.client.get(reverse('controller:checksum', args=[c.pk]), {'key': c.key})
        self.assertEqual(response.status_code, 200)


class TestRegistrationDisabled(TestOrganizationMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestRegistrationDisabled, cls).setUpClass()
        django_netjsonconfig_settings.REGISTRATION_ENABLED = False

    @classmethod
    def tearDownClass(cls):
        super(TestRegistrationDisabled, cls).tearDownClass()
        django_netjsonconfig_settings.REGISTRATION_ENABLED = True

    def test_register_404(self):
        org = self._create_org()
        response = self.client.post(REGISTER_URL, {
            'secret': TEST_ORG_SHARED_SECRET,
            'name': TEST_MACADDR_NAME,
            'mac_address': TEST_MACADDR,
            'backend': 'netjsonconfig.OpenWrt'
        })
        self.assertEqual(response.status_code, 404)
        count = Config.objects.filter(mac_address=TEST_MACADDR,
                                      organization=org).count()
        self.assertEqual(count, 0)

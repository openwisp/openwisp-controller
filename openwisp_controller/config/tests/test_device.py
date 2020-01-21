from django.core.exceptions import ValidationError
from django.test import TestCase

from openwisp_users.tests.utils import TestOrganizationMixin

from ..models import Config, Device
from . import CreateConfigTemplateMixin


class TestDevice(CreateConfigTemplateMixin, TestOrganizationMixin, TestCase):
    config_model = Config
    device_model = Device

    def test_device_with_org(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        self.assertEqual(device.organization_id, org.pk)

    def test_device_without_org(self):
        try:
            self._create_device()
        except ValidationError as e:
            self.assertIn('organization', e.message_dict)
            self.assertIn('This field', e.message_dict['organization'][0])
        else:
            self.fail('ValidationError not raised')

    def test_device_name_organization_unique_together(self):
        org = self._create_org()
        self._create_device(organization=org, name='test_device_name')
        kwargs = {
            'name': 'test_device_name',
            'organization': org
        }
        with self.assertRaises(ValidationError):
            self._create_device(**kwargs)

    def test_device_macaddress_organization_unique_together(self):
        org = self._create_org()
        self._create_device(
            organization=org,
            name='test_device1',
            mac_address='0a-1b-3c-4d-5e-6f'
        )
        kwargs = {
            'organization': org,
            'name': 'test_device2',
            'mac_address': '0a-1b-3c-4d-5e-6f'
        }
        with self.assertRaises(ValidationError):
            self._create_device(**kwargs)

    def test_device_hardwareid_unique_together(self):
        org = self._create_org()
        self._create_device(
            organization=org,
            hardware_id='098H52ST479QE053V2',
            name='test_device11',
        )
        kwargs = {
            'organization': org,
            'hardware_id': '098H52ST479QE053V2',
            'name': 'test_device22'
        }
        with self.assertRaises(ValidationError):
            self._create_device(**kwargs)

    def test_config_device_without_org(self):
        device = self._create_device(organization=self._create_org())
        self._create_config(device=device)

    def test_change_org(self):
        org1 = self._create_org()
        device = self._create_device(organization=org1)
        config = self._create_config(device=device)
        self.assertEqual(config.device.organization_id, org1.pk)
        org2 = self._create_org(name='org2')
        device.organization = org2
        device.full_clean()
        device.save()
        self.assertEqual(config.device.organization_id, org2.pk)

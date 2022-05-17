from hashlib import md5
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin
from openwisp_utils.tests import AssertNumQueriesSubTestMixin, catch_signal

from .. import settings as app_settings
from ..signals import device_group_changed, device_name_changed, management_ip_changed
from ..validators import device_name_validator, mac_address_validator
from .utils import CreateConfigTemplateMixin, CreateDeviceGroupMixin

TEST_ORG_SHARED_SECRET = 'functional_testing_secret'

Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
DeviceGroup = load_model('config', 'DeviceGroup')
_original_context = app_settings.CONTEXT.copy()


class TestDevice(
    CreateConfigTemplateMixin,
    TestOrganizationMixin,
    AssertNumQueriesSubTestMixin,
    CreateDeviceGroupMixin,
    TestCase,
):
    """
    tests for Device model
    """

    @mock.patch('openwisp_controller.config.settings.HARDWARE_ID_AS_NAME', False)
    def test_str_name(self):
        d = Device(name='test')
        self.assertEqual(str(d), 'test')

    @mock.patch('openwisp_controller.config.settings.HARDWARE_ID_ENABLED', True)
    @mock.patch('openwisp_controller.config.settings.HARDWARE_ID_AS_NAME', True)
    def test_str_hardware_id(self):
        d = Device(name='test', hardware_id='123')
        self.assertEqual(str(d), '123')

    def test_mac_address_validator(self):
        d = Device(name='test', key=self.TEST_KEY, organization=self._get_org())
        bad_mac_addresses_list = [
            '{0}:BB:CC'.format(self.TEST_MAC_ADDRESS),
            'AA:BB:CC:11:22033',
            'AA BB CC 11 22 33',
        ]
        for mac_address in bad_mac_addresses_list:
            d.mac_address = mac_address
            try:
                d.full_clean()
            except ValidationError as e:
                self.assertIn('mac_address', e.message_dict)
                self.assertEqual(
                    mac_address_validator.message, e.message_dict['mac_address'][0]
                )
            else:
                self.fail('ValidationError not raised for "{0}"'.format(mac_address))

    def test_config_status_modified(self):
        c = self._create_config(device=self._create_device(), status='applied')
        self.assertEqual(c.status, 'applied')
        c.device.name = 'test-status-modified'
        c.device.full_clean()
        c.device.save()
        c.refresh_from_db()
        self.assertEqual(c.status, 'modified')

    def test_key_validator(self):
        d = Device(
            organization=self._get_org(),
            name='test',
            mac_address=self.TEST_MAC_ADDRESS,
            hardware_id='1234',
        )
        d.key = 'key/key'
        with self.assertRaises(ValidationError):
            d.full_clean()
        d.key = 'key.key'
        with self.assertRaises(ValidationError):
            d.full_clean()
        d.key = 'key key'
        with self.assertRaises(ValidationError):
            d.full_clean()
        d.key = self.TEST_KEY
        d.full_clean()

    def test_backend(self):
        d = self._create_device()
        self.assertIsNone(d.backend)
        c = self._create_config(device=d)
        self.assertIsNotNone(d.backend)
        self.assertEqual(d.backend, c.get_backend_display())

    def test_status(self):
        d = self._create_device()
        self.assertEqual(d.status, None)
        c = self._create_config(device=d)
        self.assertIsNotNone(d.status)
        self.assertEqual(d.status, c.get_status_display())

    def test_config_model(self):
        d = Device()
        self.assertIs(d.get_config_model(), Config)

    def test_config_model_static(self):
        self.assertIs(Device.get_config_model(), Config)

    def test_get_default_templates(self):
        d = self._create_device()
        self.assertEqual(
            d.get_default_templates().count(), Config().get_default_templates().count()
        )
        self._create_config(device=d)
        self.assertEqual(
            d.get_default_templates().count(), Config().get_default_templates().count()
        )

    def test_bad_hostnames(self):
        bad_host_name_list = [
            'test device',
            'openwisp..mydomain.com',
            'openwisp,mydomain.test',
            '{0}:BB:CC'.format(self.TEST_MAC_ADDRESS),
            'AA:BB:CC:11:22033',
        ]
        for host in bad_host_name_list:
            try:
                self._create_device(name=host)
            except ValidationError as e:
                self.assertIn('name', e.message_dict)
                self.assertEqual(
                    device_name_validator.message, e.message_dict['name'][0]
                )
            else:
                self.fail(f'ValidationError not raised for "{host}"')

    def test_add_device_with_context(self):
        d = self._create_device()
        d.save()
        c = self._create_config(
            device=d,
            config={
                'openwisp': [
                    {
                        'config_name': 'controller',
                        'config_value': 'http',
                        'url': 'http://controller.examplewifiservice.com',
                        'interval': '{{ interval }}',
                        'verify_ssl': '1',
                        'uuid': 'UUID',
                        'key': self.TEST_KEY,
                    }
                ]
            },
            context={'interval': '60'},
        )
        self.assertEqual(c.json(dict=True)['openwisp'][0]['interval'], '60')

    def test_get_context_with_config(self):
        d = self._create_device()
        c = self._create_config(device=d)
        self.assertEqual(app_settings.CONTEXT, _original_context)
        self.assertEqual(d.get_context(), c.get_context())
        self.assertEqual(app_settings.CONTEXT, _original_context)

    def test_get_context_without_config(self):
        d = self._create_device()
        self.assertEqual(d.get_context(), Config(device=d).get_context())

    @mock.patch('openwisp_controller.config.settings.CONSISTENT_REGISTRATION', False)
    def test_generate_random_key(self):
        d = Device(name='test_generate_key', mac_address='00:11:22:33:44:55')
        self.assertIsNone(d.key)
        # generating key twice shall not yield same result
        self.assertNotEqual(
            d.generate_key(TEST_ORG_SHARED_SECRET),
            d.generate_key(TEST_ORG_SHARED_SECRET),
        )

    @mock.patch('openwisp_controller.config.settings.CONSISTENT_REGISTRATION', True)
    @mock.patch('openwisp_controller.config.settings.HARDWARE_ID_ENABLED', False)
    def test_generate_consistent_key_mac_address(self):
        device = Device(name='test_generate_key', mac_address='00:11:22:33:44:55')
        self.assertIsNone(device.key)
        string = '{}+{}'.format(device.mac_address, TEST_ORG_SHARED_SECRET).encode(
            'utf-8'
        )
        expected = md5(string).hexdigest()

        key = device.generate_key(TEST_ORG_SHARED_SECRET)
        self.assertEqual(key, expected)
        self.assertEqual(key, device.generate_key(TEST_ORG_SHARED_SECRET))

    @mock.patch('openwisp_controller.config.settings.CONSISTENT_REGISTRATION', True)
    @mock.patch('openwisp_controller.config.settings.HARDWARE_ID_ENABLED', True)
    def test_generate_consistent_key_mac_hardware_id(self):
        d = Device(
            name='test_generate_key',
            mac_address='00:11:22:33:44:55',
            hardware_id='1234',
        )
        self.assertIsNone(d.key)
        string = '{}+{}'.format(d.hardware_id, TEST_ORG_SHARED_SECRET).encode('utf-8')
        expected = md5(string).hexdigest()
        key = d.generate_key(TEST_ORG_SHARED_SECRET)
        self.assertEqual(key, expected)
        self.assertEqual(key, d.generate_key(TEST_ORG_SHARED_SECRET))

    def test_device_with_org(self):
        org = self._get_org()
        device = self._create_device()
        self.assertEqual(device.organization_id, org.pk)

    def test_device_without_org(self):
        try:
            self._create_device(organization=None)
        except ValidationError as e:
            self.assertIn('organization', e.message_dict)
            self.assertIn('This field', e.message_dict['organization'][0])
        else:
            self.fail('ValidationError not raised')

    def test_device_name_organization_unique_together(self):
        org = self._get_org()
        self._create_device(organization=org, name='test.device.name')
        kwargs = {'name': 'test.device.name', 'organization': org}
        with self.assertRaises(ValidationError):
            self._create_device(**kwargs)

    def test_device_group_validation(self):
        org1 = self._get_org()
        org2 = self._create_org(name='org2')
        kwargs = {
            'name': 'test.device.name',
            'organization': org1,
            'mac_address': '0a-1b-3c-4d-5e-6f',
            'group': self._create_device_group(organization=org2),
        }
        device = Device(**kwargs)
        with self.assertRaises(ValidationError) as context_manager:
            device.full_clean()
        expected_error_dict = {
            'group': [
                'Please ensure that the organization of this Device and the '
                'organization of the related Device Group match.'
            ]
        }
        self.assertEqual(context_manager.exception.message_dict, expected_error_dict)

    @mock.patch('openwisp_controller.config.settings.DEVICE_NAME_UNIQUE', False)
    def test_device_name_organization_not_unique(self):
        org = self._get_org()
        self._create_device(organization=org, name='test.device.name')
        kwargs = {
            'name': 'test.device.name',
            'organization': org,
            'mac_address': '0a-1b-3c-4d-5e-6f',
        }
        try:
            d = Device(**kwargs)
            d.full_clean()
        except ValidationError:
            self.fail('Validation error was raised')

    def test_device_macaddress_organization_unique_together(self):
        org = self._get_org()
        self._create_device(
            organization=org, name='test.device1.name', mac_address='0a-1b-3c-4d-5e-6f'
        )
        kwargs = {
            'organization': org,
            'name': 'test.device2.name',
            'mac_address': '0a-1b-3c-4d-5e-6f',
        }
        with self.assertRaises(ValidationError):
            self._create_device(**kwargs)

    def test_device_hardwareid_unique_together(self):
        org = self._get_org()
        self._create_device(
            organization=org, hardware_id='098H52ST479QE053V2', name='test.device3.name'
        )
        kwargs = {
            'organization': org,
            'hardware_id': '098H52ST479QE053V2',
            'name': 'test.device4.name',
        }
        with self.assertRaises(ValidationError):
            self._create_device(**kwargs)

    def test_config_device_without_org(self):
        device = self._create_device(organization=self._get_org())
        self._create_config(device=device)

    def test_change_org(self):
        org1 = self._get_org()
        device = self._create_device(organization=org1)
        config = self._create_config(device=device)
        self.assertEqual(config.device.organization_id, org1.pk)
        org2 = self._create_org(name='org2')
        device.organization = org2
        device.full_clean()
        device.save()
        self.assertEqual(config.device.organization_id, org2.pk)

    def test_device_get_system_context(self):
        d = self._create_device(organization=self._get_org())
        self._create_config(context={'test': 'name'}, device=d)
        d.refresh_from_db()
        system_context = d.get_system_context()
        self.assertNotIn('test', system_context.keys())

    def test_management_ip_changed_not_emitted_on_creation(self):
        with catch_signal(management_ip_changed) as handler:
            self._create_device(organization=self._get_org())
        handler.assert_not_called()

    def test_management_ip_changed_emitted(self):
        device = self._create_device(organization=self._get_org())

        with catch_signal(management_ip_changed) as handler:
            device.management_ip = '0.0.0.0'
            device.save()
        handler.assert_called_once_with(
            management_ip='0.0.0.0',
            old_management_ip=None,
            sender=Device,
            signal=management_ip_changed,
            instance=device,
        )

    def test_name_unique_validation(self):
        org = self._get_org()
        device = self._create_device(name='test', organization=org)
        self.assertEqual(device.name, 'test')
        org2 = self._create_org(name='test org2', slug='test-org2')
        device2 = self._create_device(
            name='test', organization=org2, mac_address='0a:1b:3c:4d:5e:6f'
        )
        self.assertEqual(device2.name, 'test')
        with self.assertRaises(ValidationError) as context_manager:
            self._create_device(
                name='test', organization=org2, mac_address='0a:1b:3c:4d:5e:1a'
            )
        message_dict = context_manager.exception.message_dict
        self.assertIn('__all__', message_dict)
        self.assertEqual(
            ['Device with this Name and Organization already exists.'],
            message_dict['__all__'],
        )

    def test_device_name_changed_emitted(self):
        org = self._get_org()
        device = self._create_device(name='test', organization=org)

        with catch_signal(device_name_changed) as handler:
            device.name = 'newtestdevice'
            device.save()
            self.assertEqual(device.name, 'newtestdevice')
            handler.assert_called_once_with(
                sender=Device, instance=device, signal=device_name_changed
            )

    def test_device_name_changed_not_emitted_on_creation(self):
        with catch_signal(device_name_changed) as handler:
            self._create_device(organization=self._get_org())
        handler.assert_not_called()

    def test_device_group_changed_emitted(self):
        org = self._get_org()
        device = self._create_device(name='test', organization=org)
        device_group = self._create_device_group()

        with catch_signal(device_group_changed) as handler:
            device.group = device_group
            device.save()
            handler.assert_called_once_with(
                signal=device_group_changed,
                sender=Device,
                instance=device,
                old_group_id=None,
                group_id=device_group.id,
            )

    def test_device_group_changed_not_emitted_on_creation(self):
        org = self._get_org()
        device_group = self._create_device_group(organization=org)
        with catch_signal(device_group_changed) as handler:
            self._create_device(name='test', organization=org, group=device_group)
        handler.assert_not_called()

    def test_device_field_changed_checks(self):
        self._create_device()
        device_group = self._create_device_group()
        with self.subTest('Deferred fields remained deferred'):
            device = Device.objects.only('id', 'created').first()
            device._check_changed_fields()

        with self.subTest('Deferred fields becomes non-deferred'):
            device.name = 'new-name'
            device.management_ip = '10.0.0.1'
            device.group_id = device_group.id
            # Another query is generated due to "config.set_status_modified"
            # on name change
            with self.assertNumQueries(3):
                device._check_changed_fields()

from hashlib import md5
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http.response import Http404
from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin
from openwisp_utils.tests import capture_any_output, catch_signal

from .. import settings as app_settings
from ..base.config import logger as config_model_logger
from ..controller.views import DeviceChecksumView
from ..controller.views import logger as controller_views_logger
from ..signals import (
    checksum_requested,
    config_download_requested,
    config_modified,
    config_status_changed,
    device_registered,
)
from .utils import CreateConfigTemplateMixin, TestVpnX509Mixin

TEST_MACADDR = '00:11:22:33:44:55'
TEST_ORG_SHARED_SECRET = 'functional_testing_secret'
mac_plus_secret = '%s+%s' % (TEST_MACADDR, TEST_ORG_SHARED_SECRET)
TEST_CONSISTENT_KEY = md5(mac_plus_secret.encode()).hexdigest()
TEST_MACADDR_NAME = TEST_MACADDR.replace(':', '-')

Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Ca = load_model('django_x509', 'Ca')
OrganizationConfigSettings = load_model('config', 'OrganizationConfigSettings')


class TestController(
    CreateConfigTemplateMixin, TestOrganizationMixin, TestVpnX509Mixin, TestCase
):

    """
    tests for config.controller
    """

    def setUp(self):
        self.register_url = reverse('controller:device_register')

    def _create_org(self, shared_secret=TEST_ORG_SHARED_SECRET, **kwargs):
        org = super()._create_org(**kwargs)
        OrganizationConfigSettings.objects.create(
            organization=org, shared_secret=shared_secret
        )
        return org

    def _check_header(self, response):
        self.assertEqual(response['X-Openwisp-Controller'], 'true')

    def test_device_checksum(self):
        d = self._create_device_config()
        c = d.config
        url = reverse('controller:device_checksum', args=[d.pk])
        with patch.object(
            Config, 'get_cached_checksum', return_value=c.checksum
        ) as mock:
            response = self.client.get(url, {'key': d.key, 'management_ip': '10.0.0.2'})
            mock.assert_called_once()
        self.assertEqual(response.content.decode(), c.checksum)
        self._check_header(response)
        d.refresh_from_db()
        self.assertIsNotNone(d.last_ip)
        self.assertEqual(d.management_ip, '10.0.0.2')
        # repeat without management_ip
        response = self.client.get(url, {'key': d.key})
        d.refresh_from_db()
        self.assertIsNotNone(d.last_ip)
        self.assertIsNone(d.management_ip)

    def test_device_get_object_cached(self):
        d = self._create_device_config()
        view = DeviceChecksumView()
        view.kwargs = {'pk': str(d.pk)}
        logger = controller_views_logger

        with self.subTest('check cache set'):
            with patch('django.core.cache.cache.set') as mock:
                self.assertEqual(view.get_device(), d)
                mock.assert_called_once()

        with self.subTest('check cache get'):
            with patch('django.core.cache.cache.get', return_value=d) as mock:
                view.get_device()
                mock.assert_called_once()

        with self.subTest('ensure DB is hit when cache is clear'):
            with patch.object(logger, 'debug') as mocked_debug:
                with self.assertNumQueries(1):
                    self.assertEqual(view.get_device(), d)
                    mocked_debug.assert_called_once()

        with self.subTest('ensure DB is NOT hit when cache is present'):
            with patch.object(logger, 'debug') as mocked_debug:
                with self.assertNumQueries(0):
                    self.assertEqual(view.get_device(), d)
                    mocked_debug.assert_not_called()

        with self.subTest('test manual invalidation'):
            with patch.object(logger, 'debug') as mocked_debug:
                with self.assertNumQueries(1):
                    view.get_device.invalidate(view)
                    self.assertEqual(view.get_device(), d)
                    mocked_debug.assert_called_once()

        with self.subTest('test automatic cache invalidation'):
            with patch.object(logger, 'debug') as mocked_debug:
                d.os = 'test_cache'
                d.save()
                mocked_debug.assert_called_once()

            with self.assertNumQueries(1):
                obj = view.get_device()
            self.assertEqual(obj.os, 'test_cache')

        with self.subTest('test cache invalidation on device delete'):
            d.delete()
            with self.assertNumQueries(1):
                with self.assertRaises(Http404):
                    view.get_device()

    def test_get_cached_checksum(self):
        d = self._create_device_config()
        # avoid cache to be invalidated by the update of the addresses
        d.last_ip = '127.0.0.1'
        d.management_ip = '10.0.0.2'
        d.save()

        url = reverse('controller:device_checksum', args=[d.pk])

        with self.subTest('first request does not return value from cache'):
            with self.assertNumQueries(3):
                with patch.object(
                    controller_views_logger, 'debug'
                ) as mocked_view_debug:
                    with patch.object(
                        config_model_logger, 'debug'
                    ) as mocked_config_debug:
                        self.client.get(
                            url, {'key': d.key, 'management_ip': '10.0.0.2'}
                        )
                        self.assertEqual(mocked_config_debug.call_count, 1)
                    self.assertEqual(mocked_view_debug.call_count, 1)

        with self.subTest('update_last_ip updates the cache'):
            with self.assertNumQueries(3):
                with patch.object(
                    controller_views_logger, 'debug'
                ) as mocked_view_debug:
                    with patch.object(
                        config_model_logger, 'debug'
                    ) as mocked_config_debug:
                        self.client.get(
                            url, {'key': d.key, 'management_ip': '10.0.0.3'}
                        )
                        mocked_config_debug.assert_not_called()
                    mocked_view_debug.assert_called_once_with(
                        f'invalidated view cache for device ID {d.pk.hex}'
                    )
            view = DeviceChecksumView()
            view.kwargs = {'pk': str(d.pk)}
            key = view.get_device.get_cache_key(view)
            d.refresh_from_db()
            cached_device = cache.get(key)
            self.assertEqual(cached_device, d)
            self.assertEqual(cached_device.management_ip, '10.0.0.3')

        with self.subTest('second request returns value from cache'):
            with self.assertNumQueries(0):
                with patch.object(
                    controller_views_logger, 'debug'
                ) as mocked_view_debug:
                    with patch.object(
                        config_model_logger, 'debug'
                    ) as mocked_config_debug:
                        self.client.get(
                            url, {'key': d.key, 'management_ip': '10.0.0.3'}
                        )
                        mocked_config_debug.assert_not_called()
                    mocked_view_debug.assert_not_called()

        with self.subTest('ensure cache invalidation works'):
            old_checksum = d.config.checksum
            with patch.object(config_model_logger, 'debug') as mocked_debug:
                d.config.config['general']['timezone'] = 'Europe/Rome'
                d.config.full_clean()
                d.config.save()
                del d.config.backend_instance
                self.assertNotEqual(d.config.checksum, old_checksum)
                self.assertEqual(d.config.get_cached_checksum(), d.config.checksum)
                mocked_debug.assert_called_once()

    def test_device_checksum_requested_signal_is_emitted(self):
        d = self._create_device_config()
        url = reverse('controller:device_checksum', args=[d.pk])
        with catch_signal(checksum_requested) as handler:
            response = self.client.get(url, {'key': d.key, 'management_ip': '10.0.0.2'})
            handler.assert_called_once_with(
                sender=Device,
                signal=checksum_requested,
                instance=d,
                request=response.wsgi_request,
            )

    def test_device_checksum_bad_uuid(self):
        d = self._create_device_config()
        pk = '{}-wrong'.format(d.pk)
        response = self.client.get(
            reverse('controller:device_checksum', args=[pk]), {'key': d.key}
        )
        self.assertEqual(response.status_code, 404)

    def test_device_config_download_requested_signal_is_emitted(self):
        d = self._create_device_config()
        url = reverse('controller:device_download_config', args=[d.pk])
        with catch_signal(config_download_requested) as handler:
            response = self.client.get(url, {'key': d.key, 'management_ip': '10.0.0.2'})
            handler.assert_called_once_with(
                sender=Device,
                signal=config_download_requested,
                instance=d,
                request=response.wsgi_request,
            )

    @capture_any_output()
    def test_device_checksum_400(self):
        d = self._create_device_config()
        response = self.client.get(reverse('controller:device_checksum', args=[d.pk]))
        self.assertEqual(response.status_code, 400)
        self._check_header(response)

    @capture_any_output()
    def test_device_checksum_403(self):
        d = self._create_device_config()
        response = self.client.get(
            reverse('controller:device_checksum', args=[d.pk]), {'key': 'wrong'}
        )
        self.assertEqual(response.status_code, 403)
        self._check_header(response)

    def test_device_checksum_405(self):
        d = self._create_device_config()
        response = self.client.post(
            reverse('controller:device_checksum', args=[d.pk]), {'key': d.key}
        )
        self.assertEqual(response.status_code, 405)

    def test_device_download_config(self):
        d = self._create_device_config()
        url = reverse('controller:device_download_config', args=[d.pk])
        response = self.client.get(url, {'key': d.key, 'management_ip': '10.0.0.2'})
        self.assertEqual(
            response['Content-Disposition'], 'attachment; filename=test.tar.gz'
        )
        self._check_header(response)
        d.refresh_from_db()
        self.assertIsNotNone(d.last_ip)
        self.assertEqual(d.management_ip, '10.0.0.2')
        # repeat without management_ip
        response = self.client.get(url, {'key': d.key})
        d.refresh_from_db()
        self.assertIsNotNone(d.last_ip)
        self.assertIsNone(d.management_ip)

    def test_device_download_config_bad_uuid(self):
        d = self._create_device_config()
        pk = '{}-wrong'.format(d.pk)
        response = self.client.get(
            reverse('controller:device_download_config', args=[pk]), {'key': d.key}
        )
        self.assertEqual(response.status_code, 404)

    def test_vpn_checksum_requested_signal_is_emitted(self):
        v = self._create_vpn()
        url = reverse('controller:vpn_checksum', args=[v.pk])
        with catch_signal(checksum_requested) as handler:
            response = self.client.get(url, {'key': v.key})
            handler.assert_called_once_with(
                sender=Vpn,
                signal=checksum_requested,
                instance=v,
                request=response.wsgi_request,
            )

    @capture_any_output()
    def test_device_download_config_400(self):
        d = self._create_device_config()
        response = self.client.get(
            reverse('controller:device_download_config', args=[d.pk])
        )
        self.assertEqual(response.status_code, 400)
        self._check_header(response)

    @capture_any_output()
    def test_device_download_config_403(self):
        d = self._create_device_config()
        path = reverse('controller:device_download_config', args=[d.pk])
        response = self.client.get(path, {'key': 'wrong'})
        self.assertEqual(response.status_code, 403)
        self._check_header(response)

    def test_device_download_config_405(self):
        d = self._create_device_config()
        response = self.client.post(
            reverse('controller:device_download_config', args=[d.pk]), {'key': d.key}
        )
        self.assertEqual(response.status_code, 405)

    def test_vpn_checksum(self):
        v = self._create_vpn()
        url = reverse('controller:vpn_checksum', args=[v.pk])
        response = self.client.get(url, {'key': v.key})
        self.assertEqual(response.content.decode(), v.checksum)
        self._check_header(response)

    def test_vpn_checksum_bad_uuid(self):
        v = self._create_vpn()
        pk = '{}-wrong'.format(v.pk)
        response = self.client.get(
            reverse('controller:vpn_checksum', args=[pk]), {'key': v.key}
        )
        self.assertEqual(response.status_code, 404)

    @capture_any_output()
    def test_vpn_checksum_400(self):
        v = self._create_vpn()
        response = self.client.get(reverse('controller:vpn_checksum', args=[v.pk]))
        self.assertEqual(response.status_code, 400)
        self._check_header(response)

    @capture_any_output()
    def test_vpn_checksum_403(self):
        v = self._create_vpn()
        response = self.client.get(
            reverse('controller:vpn_checksum', args=[v.pk]), {'key': 'wrong'}
        )
        self.assertEqual(response.status_code, 403)
        self._check_header(response)

    def test_vpn_checksum_405(self):
        v = self._create_vpn()
        response = self.client.post(
            reverse('controller:vpn_checksum', args=[v.pk]), {'key': v.key}
        )
        self.assertEqual(response.status_code, 405)

    def test_vpn_download_config(self):
        v = self._create_vpn()
        url = reverse('controller:vpn_download_config', args=[v.pk])
        response = self.client.get(url, {'key': v.key})
        self.assertEqual(
            response['Content-Disposition'], 'attachment; filename=test.tar.gz'
        )
        self._check_header(response)

    def test_vpn_download_config_bad_uuid(self):
        v = self._create_vpn()
        pk = '{}-wrong'.format(v.pk)
        response = self.client.get(
            reverse('controller:vpn_download_config', args=[pk]), {'key': v.key}
        )
        self.assertEqual(response.status_code, 404)

    @capture_any_output()
    def test_vpn_download_config_400(self):
        v = self._create_vpn()
        response = self.client.get(
            reverse('controller:vpn_download_config', args=[v.pk])
        )
        self.assertEqual(response.status_code, 400)
        self._check_header(response)

    @capture_any_output()
    def test_vpn_download_config_403(self):
        v = self._create_vpn()
        path = reverse('controller:vpn_download_config', args=[v.pk])
        response = self.client.get(path, {'key': 'wrong'})
        self.assertEqual(response.status_code, 403)
        self._check_header(response)

    def test_vpn_download_config_405(self):
        v = self._create_vpn()
        response = self.client.post(
            reverse('controller:vpn_download_config', args=[v.pk]), {'key': v.key}
        )
        self.assertEqual(response.status_code, 405)

    def test_register(self, **kwargs):
        options = {
            'hardware_id': '1234',
            'secret': TEST_ORG_SHARED_SECRET,
            'name': TEST_MACADDR_NAME,
            'mac_address': TEST_MACADDR,
            'backend': 'netjsonconfig.OpenWrt',
        }
        options.update(kwargs)
        org = self._get_org()
        response = self.client.post(self.register_url, options)
        lines = response.content.decode().split('\n')
        self.assertEqual(lines[0], 'registration-result: success')
        uuid = lines[1].replace('uuid: ', '')
        key = lines[2].replace('key: ', '')
        d = Device.objects.get(pk=uuid)
        self._check_header(response)
        self.assertEqual(d.key, key)
        self.assertIsNotNone(d.last_ip)
        self.assertEqual(d.mac_address, TEST_MACADDR)
        self.assertEqual(response.status_code, 201)
        count = Device.objects.filter(
            mac_address=TEST_MACADDR, organization=org
        ).count()
        self.assertEqual(count, 1)
        if 'management_ip' not in kwargs:
            self.assertIsNone(d.management_ip)
        else:
            self.assertEqual(d.management_ip, kwargs['management_ip'])
        return d

    def test_register_with_management_ip(self):
        self.test_register(management_ip='10.0.0.2')

    def test_default_template_selection_with_backend_filtering(self):
        self._create_template(
            name='t1',
            backend='netjsonconfig.OpenWisp',
            organization=self._get_org(),
            default=True,
        )
        t2 = self._create_template(
            name='t2',
            backend='netjsonconfig.OpenWrt',
            organization=self._get_org(),
            default=True,
        )
        d = self.test_register()
        qs = d.config.templates.all()
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs.first().pk, t2.pk)

    def test_register_device_info(self):
        device_model_name = 'TP-Link TL-WDR4300 v1'
        os = 'LEDE Reboot 17.01-SNAPSHOT r3270-09a8183'
        system = 'Atheros AR9344 rev 2'
        d = self.test_register(model=device_model_name, os=os, system=system)
        self.assertEqual(d.model, device_model_name)
        self.assertEqual(d.os, os)
        self.assertEqual(d.system, system)

    def test_register_failed_creation(self):
        self.test_register()
        response = self.client.post(
            self.register_url,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertContains(response, 'already exists', status_code=400)

    @capture_any_output()
    def test_register_failed_creation_wrong_backend(self):
        self.test_register()
        response = self.client.post(
            self.register_url,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.CLEARLYWRONG',
            },
        )
        self.assertContains(response, 'backend', status_code=403)

    def test_register_405(self):
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 405)

    def test_consistent_registration_new(self):
        self._create_org()
        response = self.client.post(
            self.register_url,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR,
                'key': TEST_CONSISTENT_KEY,
                'mac_address': TEST_MACADDR,
                'hardware_id': '1234',
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertEqual(response.status_code, 201)
        lines = response.content.decode().split('\n')
        self.assertEqual(lines[0], 'registration-result: success')
        uuid = lines[1].replace('uuid: ', '')
        key = lines[2].replace('key: ', '')
        new = lines[4].replace('is-new: ', '')
        self.assertEqual(new, '1')
        self.assertEqual(key, TEST_CONSISTENT_KEY)
        d = Device.objects.get(pk=uuid)
        self._check_header(response)
        self.assertEqual(d.key, TEST_CONSISTENT_KEY)
        self.assertIsNotNone(d.last_ip)

    def test_device_consistent_registration_existing(self):
        d = self._create_device_config()
        d.key = TEST_CONSISTENT_KEY
        d.save()
        response = self.client.post(
            self.register_url,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR,
                'mac_address': TEST_MACADDR,
                'key': TEST_CONSISTENT_KEY,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertEqual(response.status_code, 201)
        lines = response.content.decode().split('\n')
        self.assertEqual(lines[0], 'registration-result: success')
        uuid = lines[1].replace('uuid: ', '')
        key = lines[2].replace('key: ', '')
        hostname = lines[3].replace('hostname: ', '')
        new = lines[4].replace('is-new: ', '')
        self.assertEqual(hostname, d.name)
        self.assertEqual(new, '0')
        count = Device.objects.filter(pk=uuid, key=key, name=hostname).count()
        self.assertEqual(count, 1)

    def test_device_consistent_registration_exists_no_config(self):
        org = self._get_org()
        d = self._create_device(organization=org)
        d.key = TEST_CONSISTENT_KEY
        d.save()
        response = self.client.post(
            self.register_url,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR,
                'mac_address': TEST_MACADDR,
                'key': TEST_CONSISTENT_KEY,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertEqual(response.status_code, 201)
        lines = response.content.decode().split('\n')
        self.assertEqual(lines[0], 'registration-result: success')
        uuid = lines[1].replace('uuid: ', '')
        key = lines[2].replace('key: ', '')
        hostname = lines[3].replace('hostname: ', '')
        new = lines[4].replace('is-new: ', '')
        self.assertEqual(hostname, d.name)
        self.assertEqual(new, '0')
        count = Device.objects.filter(pk=uuid, key=key, name=hostname).count()
        self.assertEqual(count, 1)
        d.refresh_from_db()
        self.assertIsNotNone(d.config)

    def test_device_registration_update_hw_info(self):
        d = self._create_device_config()
        d.key = TEST_CONSISTENT_KEY
        d.save()
        params = {
            'secret': TEST_ORG_SHARED_SECRET,
            'name': TEST_MACADDR,
            'mac_address': TEST_MACADDR,
            'key': TEST_CONSISTENT_KEY,
            'backend': 'netjsonconfig.OpenWrt',
            'model': 'TP-Link TL-WDR4300 v2',
            'os': 'OpenWrt 18.06-SNAPSHOT r7312-e60be11330',
            'system': 'Atheros AR9344 rev 3',
        }
        self.assertNotEqual(d.os, params['os'])
        self.assertNotEqual(d.system, params['system'])
        self.assertNotEqual(d.model, params['model'])
        response = self.client.post(self.register_url, params)
        self.assertEqual(response.status_code, 201)
        d.refresh_from_db()
        self.assertEqual(d.os, params['os'])
        self.assertEqual(d.system, params['system'])
        self.assertEqual(d.model, params['model'])

    def test_device_registration_update_hw_info_no_config(self):
        d = self._create_device()
        d.key = TEST_CONSISTENT_KEY
        d.save()
        params = {
            'secret': TEST_ORG_SHARED_SECRET,
            'name': TEST_MACADDR,
            'mac_address': TEST_MACADDR,
            'key': TEST_CONSISTENT_KEY,
            'backend': 'netjsonconfig.OpenWrt',
            'model': 'TP-Link TL-WDR4300 v2',
            'os': 'OpenWrt 18.06-SNAPSHOT r7312-e60be11330',
            'system': 'Atheros AR9344 rev 3',
        }
        self.assertNotEqual(d.os, params['os'])
        self.assertNotEqual(d.system, params['system'])
        self.assertNotEqual(d.model, params['model'])
        response = self.client.post(self.register_url, params)
        self.assertEqual(response.status_code, 201)
        d.refresh_from_db()
        self.assertEqual(d.os, params['os'])
        self.assertEqual(d.system, params['system'])
        self.assertEqual(d.model, params['model'])

    def test_device_report_status_running(self):
        """
        maintained for backward compatibility
        # TODO: remove in stable version 1.0
        """
        d = self._create_device_config()
        response = self.client.post(
            reverse('controller:device_report_status', args=[d.pk]),
            {'key': d.key, 'status': 'running'},
        )
        self._check_header(response)
        d.config.refresh_from_db()
        self.assertEqual(d.config.status, 'applied')

    def test_device_report_status_applied(self):
        d = self._create_device_config()
        with catch_signal(config_status_changed) as handler:
            response = self.client.post(
                reverse('controller:device_report_status', args=[d.pk]),
                {'key': d.key, 'status': 'applied'},
            )
            d.config.refresh_from_db()
            handler.assert_called_once_with(
                sender=Config, signal=config_status_changed, instance=d.config
            )
        self._check_header(response)
        d.config.refresh_from_db()
        self.assertEqual(d.config.status, 'applied')

    def test_device_report_status_error(self):
        d = self._create_device_config()
        with catch_signal(config_status_changed) as handler:
            response = self.client.post(
                reverse('controller:device_report_status', args=[d.pk]),
                {'key': d.key, 'status': 'error'},
            )
            d.config.refresh_from_db()
            handler.assert_called_once_with(
                sender=Config, signal=config_status_changed, instance=d.config
            )
        self._check_header(response)
        d.config.refresh_from_db()
        self.assertEqual(d.config.status, 'error')

    def test_device_report_status_bad_uuid(self):
        d = self._create_device_config()
        pk = '{}-wrong'.format(d.pk)
        response = self.client.post(
            reverse('controller:device_report_status', args=[pk]), {'key': d.key}
        )
        self.assertEqual(response.status_code, 404)

    @capture_any_output()
    def test_device_report_status_400(self):
        d = self._create_device_config()
        response = self.client.post(
            reverse('controller:device_report_status', args=[d.pk])
        )
        self.assertEqual(response.status_code, 400)
        self._check_header(response)
        response = self.client.post(
            reverse('controller:device_report_status', args=[d.pk]), {'key': d.key}
        )
        self.assertEqual(response.status_code, 400)
        self._check_header(response)
        response = self.client.post(
            reverse('controller:device_report_status', args=[d.pk]), {'key': d.key}
        )
        self.assertEqual(response.status_code, 400)
        self._check_header(response)

    @capture_any_output()
    def test_device_report_status_403(self):
        d = self._create_device_config()
        response = self.client.post(
            reverse('controller:device_report_status', args=[d.pk]), {'key': 'wrong'}
        )
        self.assertEqual(response.status_code, 403)
        self._check_header(response)
        response = self.client.post(
            reverse('controller:device_report_status', args=[d.pk]),
            {'key': d.key, 'status': 'madeup'},
        )
        self.assertEqual(response.status_code, 403)
        self._check_header(response)

    def test_device_report_status_405(self):
        d = self._create_device_config()
        response = self.client.get(
            reverse('controller:device_report_status', args=[d.pk]),
            {'key': d.key, 'status': 'running'},
        )
        self.assertEqual(response.status_code, 405)

    def test_device_update_info(self):
        d = self._create_device_config()
        url = reverse('controller:device_update_info', args=[d.pk])
        params = {
            'key': d.key,
            'model': 'TP-Link TL-WDR4300 v2',
            'os': 'OpenWrt 18.06-SNAPSHOT r7312-e60be11330',
            'system': 'Atheros AR9344 rev 3',
        }
        self.assertNotEqual(d.os, params['os'])
        self.assertNotEqual(d.system, params['system'])
        self.assertNotEqual(d.model, params['model'])
        response = self.client.post(url, params)
        self.assertEqual(response.status_code, 200)
        self._check_header(response)
        d.refresh_from_db()
        self.assertEqual(d.os, params['os'])
        self.assertEqual(d.system, params['system'])
        self.assertEqual(d.model, params['model'])

        with self.subTest('ignore empty values'):
            response = self.client.post(
                url, {'key': d.key, 'model': '', 'os': '', 'system': ''}
            )
            self.assertEqual(response.status_code, 200)
            self._check_header(response)
            d.refresh_from_db()
            self.assertNotEqual(d.os, '')
            self.assertNotEqual(d.system, '')
            self.assertNotEqual(d.model, '')
            self.assertEqual(d.os, params['os'])
            self.assertEqual(d.system, params['system'])
            self.assertEqual(d.model, params['model'])

    def test_device_update_info_bad_uuid(self):
        d = self._create_device_config()
        pk = '{}-wrong'.format(d.pk)
        params = {
            'key': d.key,
            'model': 'TP-Link TL-WDR4300 v2',
            'os': 'OpenWrt 18.06-SNAPSHOT r7312-e60be11330',
            'system': 'Atheros AR9344 rev 3',
        }
        response = self.client.post(
            reverse('controller:device_update_info', args=[pk]), params
        )
        self.assertEqual(response.status_code, 404)

    def test_device_update_info_400(self):
        d = self._create_device_config()
        params = {
            'key': d.key,
            'model': (
                'TP-Link TL-WDR4300 v2 this model name is longer than 64 characters'
            ),
            'os': 'OpenWrt 18.06-SNAPSHOT r7312-e60be11330',
            'system': 'Atheros AR9344 rev 3',
        }
        response = self.client.post(
            reverse('controller:device_update_info', args=[d.pk]), params
        )
        self.assertEqual(response.status_code, 400)
        self._check_header(response)

    @capture_any_output()
    def test_device_update_info_403(self):
        d = self._create_device_config()
        params = {
            'key': 'wrong',
            'model': 'TP-Link TL-WDR4300 v2',
            'os': 'OpenWrt 18.06-SNAPSHOT r7312-e60be11330',
            'system': 'Atheros AR9344 rev 3',
        }
        response = self.client.post(
            reverse('controller:device_update_info', args=[d.pk]), params
        )
        self.assertEqual(response.status_code, 403)
        self._check_header(response)

    def test_device_update_info_405(self):
        d = self._create_device_config()
        params = {
            'key': d.key,
            'model': 'TP-Link TL-WDR4300 v2',
            'os': 'OpenWrt 18.06-SNAPSHOT r7312-e60be11330',
            'system': 'Atheros AR9344 rev 3',
        }
        response = self.client.get(
            reverse('controller:device_update_info', args=[d.pk]), params
        )
        self.assertEqual(response.status_code, 405)

    def test_device_checksum_no_config(self):
        d = self._create_device()
        response = self.client.get(
            reverse('controller:device_checksum', args=[d.pk]), {'key': d.key}
        )
        self.assertEqual(response.status_code, 404)

    def test_device_download_no_config(self):
        d = self._create_device()
        response = self.client.get(
            reverse('controller:device_download_config', args=[d.pk]), {'key': d.key}
        )
        self.assertEqual(response.status_code, 404)

    def test_device_report_status_no_config(self):
        d = self._create_device()
        response = self.client.post(
            reverse('controller:device_report_status', args=[d.pk]),
            {'key': d.key, 'status': 'running'},
        )
        self.assertEqual(response.status_code, 404)

    def test_register_failed_rollback(self):
        self._create_org()
        with patch(
            'openwisp_controller.config.base.config.AbstractConfig.full_clean'
        ) as a:
            a.side_effect = ValidationError(dict())
            options = {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR,
                'mac_address': TEST_MACADDR,
                'hardware_id': '1234',
                'backend': 'netjsonconfig.OpenWrt',
            }
            response = self.client.post(self.register_url, options)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(Device.objects.count(), 0)

    @patch('openwisp_controller.config.settings.CONSISTENT_REGISTRATION', False)
    def test_consistent_registration_disabled(self):
        self._create_org()
        response = self.client.post(
            self.register_url,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR,
                'key': TEST_CONSISTENT_KEY,
                'mac_address': TEST_MACADDR,
                'hardware_id': '1234',
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertEqual(response.status_code, 201)
        lines = response.content.decode().split('\n')
        self.assertEqual(lines[0], 'registration-result: success')
        key = lines[2].replace('key: ', '')
        new = lines[4].replace('is-new: ', '')
        self.assertEqual(new, '1')
        self.assertNotEqual(key, TEST_CONSISTENT_KEY)
        self.assertEqual(Device.objects.filter(key=TEST_CONSISTENT_KEY).count(), 0)
        self.assertEqual(Device.objects.filter(key=key).count(), 1)

    @patch('openwisp_controller.config.settings.REGISTRATION_ENABLED', False)
    def test_registration_disabled(self):
        response = self.client.post(
            self.register_url,
            {
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertEqual(response.status_code, 403)

    @patch('openwisp_controller.config.settings.REGISTRATION_SELF_CREATION', False)
    @patch('openwisp_controller.config.settings.HARDWARE_ID_ENABLED', True)
    def test_self_creation_disabled(self):
        self._create_org()
        options = {
            'secret': TEST_ORG_SHARED_SECRET,
            'name': TEST_MACADDR_NAME,
            'mac_address': TEST_MACADDR,
            'hardware_id': '1234',
            'backend': 'netjsonconfig.OpenWrt',
            'key': '800c605076cad8d777adeadf89a34b8b',
        }
        # first attempt fails because device is not present in DB
        response = self.client.post(self.register_url, options)
        self.assertEqual(response.status_code, 404)
        # once the device is created, everything works normally
        device = self._create_device(
            name=options['name'],
            mac_address=options['mac_address'],
            hardware_id=options['hardware_id'],
        )
        self.assertEqual(device.key, options['key'])
        response = self.client.post(self.register_url, options)
        self.assertEqual(response.status_code, 201)
        lines = response.content.decode().split('\n')
        self.assertEqual(lines[0], 'registration-result: success')
        uuid = lines[1].replace('uuid: ', '')
        key = lines[2].replace('key: ', '')
        created = Device.objects.get(pk=uuid)
        self.assertEqual(created.key, key)
        self.assertEqual(created.pk, device.pk)

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
            self.register_url,
            {
                'hardware_id': '1234',
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
                'tags': 'mesh',
            },
        )
        self.assertEqual(response.status_code, 201)
        d = Device.objects.filter(mac_address=TEST_MACADDR, organization=org1).first()
        self.assertEqual(d.config.templates.count(), 2)
        self.assertEqual(d.config.templates.filter(pk=t1.pk).count(), 1)
        self.assertEqual(d.config.templates.filter(pk=t_shared.pk).count(), 1)
        self.assertEqual(d.config.templates.filter(pk=t2.pk).count(), 0)

    @capture_any_output()
    def test_register_400(self):
        self._get_org()
        # missing secret
        response = self.client.post(
            self.register_url,
            {
                'hardware_id': '1234',
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertContains(response, 'secret', status_code=400)
        # missing name
        response = self.client.post(
            self.register_url,
            {
                'hardware_id': '1234',
                'mac_address': TEST_MACADDR,
                'secret': TEST_ORG_SHARED_SECRET,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertContains(response, 'name', status_code=400)
        # missing backend
        response = self.client.post(
            self.register_url,
            {
                'hardware_id': '1234',
                'mac_address': TEST_MACADDR,
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR,
            },
        )
        self.assertContains(response, 'backend', status_code=400)
        # missing mac_address
        response = self.client.post(
            self.register_url,
            {
                'hardware_id': '1234',
                'backend': 'netjsonconfig.OpenWrt',
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR,
            },
        )
        self.assertContains(response, 'mac_address', status_code=400)
        self._check_header(response)

    @capture_any_output()
    def test_register_403(self):
        self._get_org()
        # wrong secret
        response = self.client.post(
            self.register_url,
            {
                'hardware_id': '1234',
                'secret': 'WRONG',
                'name': TEST_MACADDR_NAME,
                'mac_address': TEST_MACADDR,
                'backend': 'netjsonconfig.OpenWrt',
            },
        )
        self.assertContains(response, 'error: unrecognized secret', status_code=403)
        # wrong backend
        response = self.client.post(
            self.register_url,
            {
                'hardware_id': '1234',
                'secret': TEST_ORG_SHARED_SECRET,
                'name': TEST_MACADDR,
                'mac_address': TEST_MACADDR,
                'backend': 'wrong',
            },
        )
        self.assertContains(response, 'wrong backend', status_code=403)
        self._check_header(response)

    @capture_any_output()
    def test_register_403_disabled_registration(self):
        org = self._get_org()
        org.config_settings.registration_enabled = False
        org.config_settings.save()
        response = self.client.post(
            self.register_url,
            {
                'hardware_id': '1234',
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

    @capture_any_output()
    def test_register_403_disabled_org(self):
        self._create_org(is_active=False)
        response = self.client.post(
            self.register_url,
            {
                'hardware_id': '1234',
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
        org = self._get_org()
        c = self._create_config(organization=org)
        response = self.client.get(
            reverse('controller:device_checksum', args=[c.device.pk.hex]),
            {'key': c.device.key},
        )
        self.assertEqual(response.status_code, 200)

    @patch('openwisp_controller.config.settings.REGISTRATION_ENABLED', False)
    def test_register_403_disabled_registration_setting(self):
        org = self._get_org()
        response = self.client.post(
            self.register_url,
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

    @patch.object(app_settings, 'SHARED_MANAGEMENT_IP_ADDRESS_SPACE', False)
    def test_ip_fields_not_duplicated(self):
        org1 = self._get_org()
        c1 = self._create_config(organization=org1)
        d2 = self._create_device(
            organization=org1, name='testdup', mac_address='00:11:22:33:66:77'
        )
        c2 = self._create_config(device=d2)
        org2 = self._create_org(name='org2', shared_secret='123456')
        c3 = self._create_config(organization=org2)
        with self.assertNumQueries(6):
            self.client.get(
                reverse('controller:device_checksum', args=[c3.device.pk]),
                {'key': c3.device.key, 'management_ip': '192.168.1.99'},
            )
        with self.assertNumQueries(6):
            self.client.get(
                reverse('controller:device_checksum', args=[c1.device.pk]),
                {'key': c1.device.key, 'management_ip': '192.168.1.99'},
            )
        with self.assertNumQueries(0):
            # repeat the request to test the checksum view cache interaction
            self.client.get(
                reverse('controller:device_checksum', args=[c1.device.pk]),
                {'key': c1.device.key, 'management_ip': '192.168.1.99'},
            )
        # triggers more queries because devices with conflicting addresses
        # need to be updated, luckily it does not happen often
        with self.assertNumQueries(8):
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
        self.assertIsNone(c1.device.management_ip)
        self.assertEqual(c2.device.management_ip, '192.168.1.99')
        # other organization is not affected
        self.assertEquals(c3.device.last_ip, '127.0.0.1')
        self.assertEqual(c3.device.management_ip, '192.168.1.99')

        with self.subTest('test interaction with DeviceChecksumView caching'):
            view = DeviceChecksumView()
            view.kwargs = {'pk': str(c1.device.pk)}
            cached_device1 = view.get_device()
            self.assertIsNone(cached_device1.management_ip)

    @patch.object(app_settings, 'SHARED_MANAGEMENT_IP_ADDRESS_SPACE', True)
    def test_organization_shares_management_ip_address_space(self):
        org1 = self._get_org()
        org1_config = self._create_config(organization=org1)
        org2 = self._create_org(name='org2', shared_secret='org2')
        org2_config = self._create_config(organization=org2)
        with self.assertNumQueries(6):
            self.client.get(
                reverse('controller:device_checksum', args=[org1_config.device_id]),
                {'key': org1_config.device.key, 'management_ip': '192.168.1.99'},
            )
        # Device from another organization sends conflicting management IP
        # Extra queries due to conflict resolution
        with self.assertNumQueries(8):
            self.client.get(
                reverse('controller:device_checksum', args=[org2_config.device_id]),
                {'key': org2_config.device.key, 'management_ip': '192.168.1.99'},
            )
        org1_config.refresh_from_db()
        org2_config.refresh_from_db()
        # device previously having the IP now won't have it anymore
        self.assertIsNone(org1_config.device.management_ip)
        self.assertEqual(org2_config.device.management_ip, '192.168.1.99')
        self.assertNotEqual(org1_config.device.last_ip, org2_config.device.last_ip)

    # simulate public IP by mocking the
    # method which tells us if the ip is private or not
    @patch('ipaddress.IPv4Address.is_private', False)
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

    def test_config_modified_not_sent_in_registration(self):
        options = {
            'hardware_id': '1234',
            'secret': TEST_ORG_SHARED_SECRET,
            'name': TEST_MACADDR_NAME,
            'mac_address': TEST_MACADDR,
            'backend': 'netjsonconfig.OpenWrt',
        }
        org = self._get_org()
        qs = Device.objects.filter(mac_address=TEST_MACADDR, organization=org)
        self.assertEqual(qs.count(), 0)
        # create default template to ensure the config object will be changed
        self._create_template(name='t1', organization=org, default=True)
        # ensure config_modified signal not emitted
        with catch_signal(config_modified) as handler:
            self.client.post(self.register_url, options)
            handler.assert_not_called()
        self.assertEqual(qs.count(), 1)

    def test_device_registered_signal(self):
        with catch_signal(device_registered) as handler:
            device = self.test_register()
            handler.assert_called_once_with(
                sender=Device, signal=device_registered, instance=device, is_new=True
            )

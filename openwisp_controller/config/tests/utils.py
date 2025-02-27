"""
test utilities shared among test classes
these mixins are reused also in openwisp2
change with care.
"""

from copy import deepcopy
from unittest import mock
from uuid import uuid4

from django.db.utils import DEFAULT_DB_ALIAS
from openwisp_ipam.tests import CreateModelsMixin as CreateIpamModelsMixin
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from ...pki.tests.utils import TestPkiMixin

Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
DeviceGroup = load_model('config', 'DeviceGroup')
Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')


class CreateDeviceMixin(TestOrganizationMixin):
    TEST_MAC_ADDRESS = '00:11:22:33:44:55'

    def _create_device(self, **kwargs):
        options = dict(
            name='default.test.device',
            organization=self._get_org(),
            mac_address=self.TEST_MAC_ADDRESS,
            hardware_id=str(uuid4().hex),
            model='TP-Link TL-WDR4300 v1',
            os='LEDE Reboot 17.01-SNAPSHOT r3313-c2999ef',
        )
        options.update(kwargs)
        d = Device(**options)
        d.full_clean()
        d.save()
        return d

    def _create_device_config(self, device_opts=None, config_opts=None):
        device_opts = device_opts or {}
        config_opts = config_opts or {}
        device_opts.setdefault('name', 'test')
        d = self._create_device(**device_opts)
        config_opts['device'] = d
        self._create_config(**config_opts)
        return d


class CreateConfigMixin(CreateDeviceMixin):
    TEST_KEY = 'w1gwJxKaHcamUw62TQIPgYchwLKn3AA0'

    def _create_config(self, **kwargs):
        options = dict(backend='netjsonconfig.OpenWrt', config={'general': {}})
        options.update(kwargs)
        if 'device' not in kwargs:
            options['device'] = self._create_device(
                organization=self._get_org(), name='test-device'
            )
        templates = options.pop('templates', [])
        c = Config(**options)
        if templates:
            c.templates.set(templates)
        c.full_clean()
        c.save()
        return c


class CreateTemplateMixin(object):
    def _create_template(self, **kwargs):
        model_kwargs = {
            'name': 'test-template',
            'backend': 'netjsonconfig.OpenWrt',
            'config': {'interfaces': [{'name': 'eth0', 'type': 'ethernet'}]},
        }
        model_kwargs.update(kwargs)
        t = Template(**model_kwargs)
        t.full_clean()
        t.save()
        return t


class CreateVpnMixin(object):
    ca_model = Ca
    cert_model = Cert
    _BACKENDS = {
        'openvpn': 'openwisp_controller.vpn_backends.OpenVpn',
        'wireguard': 'openwisp_controller.vpn_backends.Wireguard',
        'vxlan': 'openwisp_controller.vpn_backends.VxlanWireguard',
        'zerotier': 'openwisp_controller.vpn_backends.ZeroTier',
    }

    _dh = """-----BEGIN DH PARAMETERS-----
MIIBCAKCAQEAqzVRdXJ/R4L/sq0bhgCXnFy9M5lOYkux9SIoe8hvrcqNAvJu/V+g
Xl+pFR8I8Er70E2wIv2b3exThpa3JrJiAdNQaAmZ9pUcJZCqI3dCoJk7UmlIEKPB
eUGdsrCuqpicJiavhj2ESb2p5tnWCrydgY9Vpr1ZrMoCLVO0wgMrm+MOdnscuMv8
6bIYReXcA+dQaT4jr/dvemtCV3r7NByMcq5gVqb2enNpq3SEkLLlJC0rHt1ewiHq
FMbH5wGVnwU3rZf+/kv/ySddQRj9ZeR9LFsXYM0sXJNpd5rO/XZqoI8edVX+lPh8
UqzLuoNWCyj8KCicbA7tiBxX+2zgQpch8wIBAg==
-----END DH PARAMETERS-----\n"""
    _vpn_config = {
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
        ],
        'wireguard': [{'name': 'wg0', 'port': 51820}],
    }

    @mock.patch(
        'openwisp_controller.config.base.vpn.AbstractVpn.dhparam',
        mock.MagicMock(return_value=_dh),
    )
    def _create_vpn(self, ca_options={}, **kwargs):
        options = dict(
            name='test',
            host='vpn1.test.com',
            backend=self._BACKENDS['openvpn'],
            config=self._vpn_config,
            dh=self._dh,
        )
        options.update(**kwargs)
        if 'ca' not in options:
            options['ca'] = self._create_ca(**ca_options)
        vpn = Vpn(**options)
        vpn.full_clean()
        vpn.save()
        return vpn


class TestWireguardVpnMixin(CreateIpamModelsMixin):
    def _create_wireguard_vpn(self, config=None, **kwargs):
        if config is None:
            config = {'wireguard': [{'name': 'wg0', 'port': 51820}]}
        org = kwargs.get('organization', None)
        if 'subnet' not in kwargs:
            kwargs['subnet'] = self._create_subnet(
                name='wireguard test', subnet='10.0.0.0/16', organization=org
            )
        vpn_options = {
            'backend': 'openwisp_controller.vpn_backends.Wireguard',
            'config': config,
            'name': 'test',
            'host': 'vpn1.test.com',
        }
        vpn_options.update(kwargs)
        vpn = Vpn(**vpn_options)
        vpn.full_clean()
        vpn.save()
        return vpn

    def _create_wireguard_vpn_template(self, auto_cert=True, **kwargs):
        vpn = self._create_wireguard_vpn()
        org1 = kwargs.get('organization', vpn.organization)
        template = self._create_template(
            name='wireguard',
            type='vpn',
            vpn=vpn,
            organization=org1,
            auto_cert=auto_cert,
        )
        device = self._create_device_config()
        device.config.templates.add(template)
        return device, vpn, template


class TestVxlanWireguardVpnMixin(CreateIpamModelsMixin):
    def _create_vxlan_tunnel(self, config=None):
        if config is None:
            config = {'wireguard': [{'name': 'wg0', 'port': 51820}]}
        org = self._get_org()
        subnet = self._create_subnet(
            name='wireguard test', subnet='10.0.0.0/16', organization=org
        )
        tunnel = self._create_vpn(
            organization=org,
            backend=self._BACKENDS['vxlan'],
            config=config,
            subnet=subnet,
            ca=None,
        )
        return tunnel, subnet

    def _create_vxlan_vpn_template(self):
        vpn, subnet = self._create_vxlan_tunnel()
        org1 = vpn.organization
        template = self._create_template(
            name='vxlan-wireguard',
            type='vpn',
            vpn=vpn,
            organization=org1,
            auto_cert=True,
        )
        device = self._create_device_config()
        device.config.templates.add(template)
        return device, vpn, template


class TestZeroTierVpnMixin(CreateIpamModelsMixin):
    _TEST_ZT_NETWORK_CONFIG = {
        'authTokens': [None],
        'authorizationEndpoint': '',
        'capabilities': [],
        'clientId': '',
        'creationTime': 1690149114186,
        'dns': {'domain': '', 'servers': []},
        'enableBroadcast': True,
        'id': '9536600adf2e3db9',
        'ipAssignmentPools': [],
        'mtu': 2800,
        'multicastLimit': 32,
        'name': 'test-zerotier-vpn',
        'nwid': '9536600adf2e3db9',
        'objtype': 'network',
        'private': True,
        'remoteTraceLevel': 0,
        'remoteTraceTarget': None,
        'revision': 2,
        'routes': [{'target': '0.0.0.0/24', 'via': None}],
        'rules': [
            {'etherType': 2048, 'not': True, 'or': False, 'type': 'MATCH_ETHERTYPE'},
            {'etherType': 2054, 'not': True, 'or': False, 'type': 'MATCH_ETHERTYPE'},
            {'etherType': 34525, 'not': True, 'or': False, 'type': 'MATCH_ETHERTYPE'},
            {'type': 'ACTION_DROP'},
            {'type': 'ACTION_ACCEPT'},
        ],
        'rulesSource': '',
        'ssoEnabled': False,
        'tags': [],
        'v4AssignMode': {'zt': False},
        'v6AssignMode': {'6plane': False, 'rfc4193': False, 'zt': False},
    }
    _TEST_ZT_NODE_CONFIG = {
        'address': '9536600adf',
        'clock': 1690196627974,
        'config': {
            'settings': {
                'allowTcpFallbackRelay': True,
                'forceTcpRelay': False,
                'listeningOn': [
                    '172.17.0.1/9993',
                    '172.18.0.1/9993',
                ],
                'portMappingEnabled': True,
                'primaryPort': 9993,
                'secondaryPort': 64166,
                'softwareUpdate': 'disable',
                'softwareUpdateChannel': 'release',
                'surfaceAddresses': ['103.172.72.9/36684'],
                'tertiaryPort': 0,
            }
        },
        'online': True,
        'planetWorldId': 149604618,
        'planetWorldTimestamp': 1644592324813,
        'publicIdentity': (
            '9536600adf:0:cd1e650df2b2e77abe8433'
            'b44960b23823451216aeb7a0158eb6f3745'
            'eb17bf724457c07e29de8b965871479ca77'
            'be46261b6d570db6ab86fa960382ac89c8a1'
        ),
        'tcpFallbackActive': False,
        'version': '1.10.6',
        'versionBuild': 0,
        'versionMajor': 1,
        'versionMinor': 10,
        'versionRev': 6,
    }

    _TEST_ZT_MEMBER_CONFIG = {
        'activeBridge': False,
        'address': '89e327619d',
        'authenticationExpiryTime': 0,
        'authorized': True,
        'capabilities': [],
        'creationTime': 1690971894880,
        'id': '89e327619d',
        'identity': (
            '89e327619d:0:022a66a1939f1e786e45be7f46'
            'baeac8c59e07a6a746eb02d8c42036072d0c67c'
            '7eb8674d5c4a9869cc78b84549496c5e64b7552'
            'def984effd9ea92ef5c109a9'
        ),
        'ipAssignments': ['10.0.0.155'],
        'lastAuthorizedCredential': None,
        'lastAuthorizedCredentialType': 'api',
        'lastAuthorizedTime': 1690971894990,
        'lastDeauthorizedTime': 0,
        'noAutoAssignIps': False,
        'nwid': '9536600adf1570e3',
        'objtype': 'member',
        'remoteTraceLevel': 0,
        'remoteTraceTarget': None,
        'revision': 2,
        'ssoExempt': False,
        'tags': [],
        'vMajor': 1,
        'vMinor': 10,
        'vProto': 12,
        'vRev': 3,
    }

    def _get_mock_response(self, status_code, response=None, err=None, exc=None):
        response = (
            deepcopy(self._TEST_ZT_NETWORK_CONFIG) if response is None else response
        )
        mock_response = mock.Mock(status_code=status_code, reason=err)
        mock_response.json.return_value = response
        mock_response.raise_for_status.side_effect = exc
        return mock_response

    def _create_zerotier_vpn(self, config=None, **kwargs):
        if config is None:
            config = {
                'zerotier': [
                    {
                        'private': True,
                        'enableBroadcast': True,
                        'mtu': 2800,
                        'multicastLimit': 32,
                    }
                ]
            }
        org = kwargs.get('organization', None)
        if 'subnet' not in kwargs:
            kwargs['subnet'] = self._create_subnet(
                name='test-zerotier-subnet', subnet='10.0.0.0/16', organization=org
            )
        vpn_options = {
            'backend': 'openwisp_controller.vpn_backends.ZeroTier',
            'config': config,
            'name': 'test-zerotier-vpn',
            'host': 'localhost:9993',
            'auth_token': 'a6uo9egbutyg9i399x3aocan',
        }
        vpn_options.update(kwargs)
        vpn = Vpn(**vpn_options)
        vpn.full_clean()
        vpn.save()
        return vpn

    def _create_zerotier_vpn_template(self, auto_cert=True, **kwargs):
        vpn = self._create_zerotier_vpn()
        org1 = kwargs.get('organization', vpn.organization)
        template = self._create_template(
            name='test-zerotier-template',
            type='vpn',
            vpn=vpn,
            organization=org1,
            auto_cert=auto_cert,
        )
        device = self._create_device_config()
        device.config.templates.add(template)
        return device, vpn, template


class TestVpnX509Mixin(CreateVpnMixin, TestPkiMixin):
    def _create_vpn(self, ca_options={}, **kwargs):
        if 'ca' not in kwargs:
            org = kwargs.get('organization')
            name = org.name if org else kwargs.get('name') or 'test'
            ca_options['name'] = '{0}-ca'.format(name)
            ca_options['common_name'] = '{0}-ca-{1}'.format(name, uuid4())
            ca_options['organization'] = org
        return super()._create_vpn(ca_options, **kwargs)


class CreateConfigTemplateMixin(CreateTemplateMixin, CreateConfigMixin):
    def assertNumQueries(self, num, func=None, *args, using=DEFAULT_DB_ALIAS, **kwargs):
        # NOTE: Do not remove this. It is required by
        # "openwisp_controller.subnet_division". Check
        # "openwisp_controller.subnet_division.apps" for details.
        return super().assertNumQueries(num, func=func, *args, using=using, **kwargs)

    def _create_config(self, **kwargs):
        if 'device' not in kwargs:
            kwargs['device'] = self._create_device(
                name='test-device', organization=kwargs.pop('organization')
            )
        return super()._create_config(**kwargs)


class CreateDeviceGroupMixin(TestOrganizationMixin):
    def _create_device_group(self, **kwargs):
        options = {
            'name': 'Routers',
            'description': 'Group for all routers',
            'context': {},
        }
        options.update(kwargs)
        if 'organization' not in options:
            options['organization'] = self._get_org()
        device_group = DeviceGroup(**options)
        device_group.full_clean()
        device_group.save()
        return device_group

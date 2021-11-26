from unittest.mock import patch

from django.test import TransactionTestCase
from django.urls import reverse
from swapper import load_model

from openwisp_users.tests.utils import TestMultitenantAdminMixin

from .helpers import SubnetDivisionTestMixin

Subnet = load_model('openwisp_ipam', 'Subnet')
Device = load_model('config', 'Device')


class TestSubnetAdmin(
    SubnetDivisionTestMixin, TestMultitenantAdminMixin, TransactionTestCase
):
    ipam_label = 'openwisp_ipam'
    config_label = 'config'

    def setUp(self):
        org = self._get_org()
        self.master_subnet = self._get_master_subnet()
        vpn_server = self._create_wireguard_vpn(
            subnet=self.master_subnet, organization=org
        )
        self.template = self._create_template(
            name='vpn-test', type='vpn', vpn=vpn_server, organization=org
        )
        self.config = self._create_config(organization=org)
        self.rule = self._get_vpn_subdivision_rule(number_of_ips=1, number_of_subnets=1)
        self.config.templates.add(self.template)
        admin = self._get_admin()
        self.client.force_login(admin)

    def test_related_links(self):
        device_changelist = reverse(f'admin:{self.config_label}_device_changelist')
        subnet = self.config.subnetdivisionindex_set.first().subnet
        url = f'{device_changelist}?subnet={subnet.subnet}'
        with self.subTest('Test changelist view'):
            response = self.client.get(
                reverse(f'admin:{self.ipam_label}_subnet_changelist')
            )
            self.assertContains(
                response,
                f'<a href="{url}">{self.config.device.name}</a>',
            )

        with self.subTest('Test change view'):
            response = self.client.get(
                reverse(f'admin:{self.ipam_label}_subnet_change', args=[subnet.pk])
            )
            self.assertContains(
                response,
                f'<a href="{url}">{self.config.device.name}</a>',
            )

    def test_device_filter(self):
        subnet_changelist = reverse(f'admin:{self.ipam_label}_subnet_changelist')
        config2 = self._create_config(
            device=self._create_device(name='device-2', mac_address='00:11:22:33:44:56')
        )
        config2.templates.add(self.template)
        url = f'{subnet_changelist}?device={self.config.device.name}'
        response = self.client.get(url)
        self.assertContains(
            response,
            self.config.device.name,
        )
        self.assertNotContains(response, config2.device.name)

    def test_device_filter_mutitenancy(self):
        org2 = self._create_org(name='org2')
        master_subnet2 = self._get_master_subnet(organization=org2)
        template2 = self._create_template(
            name='vpn-test',
            type='vpn',
            vpn=self._create_wireguard_vpn(subnet=master_subnet2, organization=org2),
            organization=org2,
        )
        self.rule = self._get_vpn_subdivision_rule(
            number_of_ips=1,
            number_of_subnets=1,
            organization=org2,
            master_subnet=master_subnet2,
        )
        config2 = self._create_config(
            device=self._create_device(name='org2-device', organization=org2)
        )
        config2.templates.add(template2)

        org2_user = self._create_org_user(
            organization=org2, is_admin=True, user=self._create_operator()
        )
        org2_user.user.user_permissions.add(*self.get_operator_permissions())
        self.client.logout()
        self.client.force_login(org2_user.user)

        response = self.client.get(
            reverse(f'admin:{self.ipam_label}_subnet_changelist')
        )
        self.assertNotContains(response, self.config.device.name)
        self.assertContains(response, config2.device.name)

    @patch('openwisp_controller.subnet_division.settings.HIDE_GENERATED_SUBNETS', True)
    def test_hide_generated_subnets(self):
        with self.subTest('Test SubnetAdmin'):
            response = self.client.get(
                reverse(f'admin:{self.ipam_label}_subnet_changelist')
            )
            self.assertNotContains(response, f'{self.rule.label}_subnet')

        with self.subTest('Test IpAddressAdmin'):
            response = self.client.get(
                reverse(f'admin:{self.ipam_label}_ipaddress_changelist')
            )
            self.assertNotContains(response, f'{self.rule.label}_subnet')

    def test_not_hide_generated_subnets(self):
        with self.subTest('Test SubnetAdmin'):
            response = self.client.get(
                reverse(f'admin:{self.ipam_label}_subnet_changelist')
            )
            self.assertContains(response, f'{self.rule.label}_subnet')

        with self.subTest('Test IpAddressAdmin'):
            response = self.client.get(
                reverse(f'admin:{self.ipam_label}_ipaddress_changelist')
            )
            self.assertContains(response, f'{self.rule.label}_subnet')


class TestIPAdmin(
    SubnetDivisionTestMixin, TestMultitenantAdminMixin, TransactionTestCase
):
    ipam_label = 'openwisp_ipam'

    def setUp(self):
        org = self._get_org()
        self.master_subnet = self._get_master_subnet()
        vpn_server = self._create_wireguard_vpn(
            subnet=self.master_subnet, organization=org
        )
        self.template = self._create_template(
            name='vpn-test', type='vpn', vpn=vpn_server, organization=org
        )
        self.config = self._create_config(organization=org)
        self.rule = self._get_vpn_subdivision_rule(number_of_ips=1, number_of_subnets=1)
        self.config.templates.add(self.template)
        admin = self._get_admin()
        self.client.force_login(admin)

    def test_provisioned_ip_readonly_change_view(self):
        ip_id = self.rule.subnetdivisionindex_set.filter(ip__isnull=False).first().ip_id
        response = self.client.get(
            reverse(f'admin:{self.ipam_label}_ipaddress_change', args=[ip_id])
        )
        self.assertNotContains(
            response, '<select name="subnet" required="" id="id_subnet"'
        )
        self.assertNotContains(response, '<input type="text" name="ip_address"')


class TestDeviceAdmin(
    SubnetDivisionTestMixin, TestMultitenantAdminMixin, TransactionTestCase
):
    ipam_label = 'openwisp_ipam'
    config_label = 'config'

    def setUp(self):
        org = self._get_org()
        self.master_subnet = self._get_master_subnet()
        vpn_server = self._create_wireguard_vpn(
            subnet=self.master_subnet, organization=org
        )
        template = self._create_template(
            name='vpn-test', type='vpn', vpn=vpn_server, organization=org
        )
        self.config = self._create_config(organization=org)
        self.rule = self._get_vpn_subdivision_rule(number_of_ips=1, number_of_subnets=1)
        self.config.templates.add(template)
        admin = self._get_admin()
        self.client.force_login(admin)

    def test_subnet_filter(self):
        device_changelist = reverse(f'admin:{self.config_label}_device_changelist')
        device2 = self._create_device(name='device-2', mac_address='00:11:22:33:44:56')
        subnet = self.config.subnetdivisionindex_set.first().subnet
        url = (
            f'{device_changelist}?subnet={subnet.subnet}'
            '&config__backend__exact=netjsonconfig.OpenWrt'
        )
        response = self.client.get(url)
        self.assertContains(
            response,
            self.config.device.name,
        )
        self.assertNotContains(response, device2.name)

    def test_subnet_filter_mutitenancy(self):
        org2 = self._create_org(name='org2')
        master_subnet2 = self._get_master_subnet(organization=org2)
        template2 = self._create_template(
            name='vpn-test',
            type='vpn',
            vpn=self._create_wireguard_vpn(subnet=master_subnet2, organization=org2),
            organization=org2,
        )
        self.rule = self._get_vpn_subdivision_rule(
            number_of_ips=1,
            number_of_subnets=1,
            organization=org2,
            master_subnet=master_subnet2,
        )
        config2 = self._create_config(
            device=self._create_device(name='org2-device', organization=org2)
        )
        config2.templates.add(template2)

        org2_owner = self._create_org_user(
            organization=org2, is_admin=True, user=self._create_operator()
        )
        org2_owner.user.user_permissions.add(*self.get_operator_permissions())
        self.client.logout()
        self.client.force_login(org2_owner.user)

        response = self.client.get(
            reverse(f'admin:{self.config_label}_device_changelist')
        )
        self.assertNotContains(response, self.config.device.name)
        self.assertContains(response, config2.device.name)

    def test_delete_device(self):
        device_response = self.client.post(
            reverse(
                f'admin:{self.config_label}_device_delete',
                args=[self.config.device_id],
            ),
            {'post': 'yes'},
        )
        self.assertEqual(device_response.status_code, 302)
        self.assertEqual(Device.objects.count(), 0)
        self.assertEqual(self.subnet_query.exclude(id=self.master_subnet.id).count(), 0)

        subnet_response = self.client.get(
            reverse(f'admin:{self.ipam_label}_subnet_changelist')
        )
        self.assertEqual(subnet_response.status_code, 200)
        self.assertContains(subnet_response, self.config.device.name, 1)

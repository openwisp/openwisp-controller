from unittest.mock import patch

from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from swapper import load_model

from openwisp_controller.config.tests.test_admin import TestDeviceAdminMixin
from openwisp_controller.config.tests.utils import (
    TestVpnX509Mixin,
    TestWireguardVpnMixin,
)
from openwisp_users.tests.utils import TestMultitenantAdminMixin

from .helpers import SubnetDivisionAdminTestMixin, SubnetDivisionTestMixin

Subnet = load_model("openwisp_ipam", "Subnet")
Device = load_model("config", "Device")
Config = load_model("config", "Config")


class TestSubnetAdmin(
    SubnetDivisionAdminTestMixin,
    TestWireguardVpnMixin,
    TestMultitenantAdminMixin,
    TestCase,
):
    ipam_label = "openwisp_ipam"
    config_label = "config"

    def test_related_links(self):
        device_changelist = reverse(f"admin:{self.config_label}_device_changelist")
        subnet = self.config.subnetdivisionindex_set.first().subnet
        url = f"{device_changelist}?subnet={subnet.subnet}"
        with self.subTest("Test changelist view"):
            response = self.client.get(
                reverse(f"admin:{self.ipam_label}_subnet_changelist")
            )
            self.assertContains(
                response,
                f'<a href="{url}">{self.config.device.name}</a>',
            )

        with self.subTest("Test change view"):
            response = self.client.get(
                reverse(f"admin:{self.ipam_label}_subnet_change", args=[subnet.pk])
            )
            self.assertContains(
                response,
                f'<a href="{url}">{self.config.device.name}</a>',
            )

    def test_device_filter(self):
        subnet_changelist = reverse(f"admin:{self.ipam_label}_subnet_changelist")
        config2 = self._create_config(
            device=self._create_device(name="device-2", mac_address="00:11:22:33:44:56")
        )
        self._mock_subnet_division_rule(config2, self.master_subnet, self.rule)
        url = f"{subnet_changelist}?device={self.config.device.name}"
        response = self.client.get(url)
        self.assertContains(
            response,
            self.config.device.name,
        )
        self.assertNotContains(response, config2.device.name)

    def test_device_filter_mutitenancy(self):
        # Create subnet and device for another organization
        org2 = self._create_org(name="org2")
        master_subnet2 = self._get_master_subnet(organization=org2)
        config2 = self._create_config(
            device=self._create_device(name="org2-device", organization=org2)
        )
        rule2 = self._get_vpn_subdivision_rule(
            number_of_ips=1,
            number_of_subnets=1,
            organization=org2,
            master_subnet=master_subnet2,
        )
        self._mock_subnet_division_rule(config2, master_subnet2, rule2)
        administrator = self._create_administrator([org2])
        self.client.logout()
        self.client.force_login(administrator)

        response = self.client.get(
            reverse(f"admin:{self.ipam_label}_subnet_changelist")
        )
        self.assertNotContains(response, self.config.device.name)
        self.assertContains(response, config2.device.name)

    def test_vpn_filter(self):
        subnet_changelist = reverse(f"admin:{self.ipam_label}_subnet_changelist")
        org = self._get_org()
        subnet1 = self._create_subnet(
            name="Subnet 1", subnet="172.16.0.0/24", organization=org
        )
        subnet2 = self._create_subnet(
            name="Subnet 2", subnet="172.16.1.0/24", organization=org
        )
        vpn = self._create_wireguard_vpn(subnet=subnet1, organization=org)
        url = f"{subnet_changelist}?vpn={vpn.id}"
        response = self.client.get(url)
        self.assertContains(
            response,
            subnet1.name,
        )
        self.assertNotContains(response, self.master_subnet.name)
        self.assertNotContains(response, subnet2.name)

    def test_vpn_filter_mutitenancy(self):
        subnet_changelist = reverse(f"admin:{self.ipam_label}_subnet_changelist")
        org1 = self._create_org(name="org1")
        org2 = self._create_org(name="org2")
        subnet1 = self._create_subnet(
            name="Subnet 1", subnet="172.16.0.0/24", organization=org1
        )
        subnet2 = self._create_subnet(
            name="Subnet 2", subnet="172.16.1.0/24", organization=org2
        )
        vpn1 = self._create_wireguard_vpn(subnet=subnet1, organization=org1)
        administrator = self._create_administrator([org2])
        self.client.logout()
        self.client.force_login(administrator)
        url = f"{subnet_changelist}?vpn={vpn1.id}"
        response = self.client.get(url)
        self.assertNotContains(
            response,
            subnet1.name,
        )
        self.assertNotContains(
            response,
            subnet2.name,
        )

    @patch("openwisp_controller.subnet_division.settings.HIDE_GENERATED_SUBNETS", True)
    def test_hide_generated_subnets(self):
        with self.subTest("Test SubnetAdmin"):
            response = self.client.get(
                reverse(f"admin:{self.ipam_label}_subnet_changelist")
            )
            self.assertNotContains(response, f"{self.rule.label}_subnet")

        with self.subTest("Test IpAddressAdmin"):
            response = self.client.get(
                reverse(f"admin:{self.ipam_label}_ipaddress_changelist")
            )
            self.assertNotContains(response, f"{self.rule.label}_subnet")

    def test_not_hide_generated_subnets(self):
        with self.subTest("Test SubnetAdmin"):
            response = self.client.get(
                reverse(f"admin:{self.ipam_label}_subnet_changelist")
            )
            self.assertContains(response, "TEST_subnet")

        with self.subTest("Test IpAddressAdmin"):
            response = self.client.get(
                reverse(f"admin:{self.ipam_label}_ipaddress_changelist")
            )
            self.assertContains(response, "TEST_subnet")

    def test_subnet_division_rule_filter(self):
        device_subnet = self._create_subnet(
            name="Device Subnet", subnet="192.168.0.0/16"
        )
        vpn_subnet = self._create_subnet(name="VPN Subnet", subnet="172.16.0.0/16")
        device_rule = self._get_device_subdivision_rule(
            master_subnet=device_subnet, label="LAN"
        )
        vpn_rule = self._get_vpn_subdivision_rule(master_subnet=vpn_subnet, label="VPN")

        path = reverse(f"admin:{self.ipam_label}_subnet_changelist")
        response = self.client.get(path)
        self.assertContains(response, vpn_subnet.name)
        self.assertContains(response, device_subnet.name)

        url = f"{path}?rule_type={vpn_rule.type}"
        response = self.client.get(url)
        self.assertContains(response, vpn_subnet.name)
        self.assertNotContains(response, device_subnet.name)

        url = f"{path}?rule_type={device_rule.type}"
        response = self.client.get(url)
        self.assertContains(response, device_subnet.name)
        self.assertNotContains(response, vpn_subnet.name)


class TestIPAdmin(SubnetDivisionAdminTestMixin, TestMultitenantAdminMixin, TestCase):
    ipam_label = "openwisp_ipam"

    def test_provisioned_ip_readonly_change_view(self):
        ip_id = self.rule.subnetdivisionindex_set.filter(ip__isnull=False).first().ip_id
        response = self.client.get(
            reverse(f"admin:{self.ipam_label}_ipaddress_change", args=[ip_id])
        )
        self.assertNotContains(
            response, '<select name="subnet" required="" id="id_subnet"'
        )
        self.assertNotContains(response, '<input type="text" name="ip_address"')


class TestDeviceAdmin(
    SubnetDivisionAdminTestMixin, TestMultitenantAdminMixin, TestCase
):
    ipam_label = "openwisp_ipam"
    config_label = "config"

    def test_subnet_filter(self):
        device_changelist = reverse(f"admin:{self.config_label}_device_changelist")
        device2 = self._create_device(name="device-2", mac_address="00:11:22:33:44:56")
        subnet = self.config.subnetdivisionindex_set.first().subnet
        url = (
            f"{device_changelist}?subnet={subnet.subnet}"
            "&config__backend__exact=netjsonconfig.OpenWrt"
        )
        response = self.client.get(url)
        self.assertContains(
            response,
            self.config.device.name,
        )
        self.assertNotContains(response, device2.name)

    def test_subnet_filter_multitenancy(self):
        # Create subnet and device for another organization
        org2 = self._create_org(name="org2")
        master_subnet2 = self._get_master_subnet(organization=org2)
        config2 = self._create_config(
            device=self._create_device(name="org2-device", organization=org2)
        )
        rule2 = self._get_vpn_subdivision_rule(
            number_of_ips=1,
            number_of_subnets=1,
            organization=org2,
            master_subnet=master_subnet2,
        )
        self._mock_subnet_division_rule(config2, master_subnet2, rule2)
        administrator = self._create_administrator([org2])
        self.client.logout()
        self.client.force_login(administrator)

        response = self.client.get(
            reverse(f"admin:{self.config_label}_device_changelist")
        )
        self.assertNotContains(response, self.config.device.name)
        self.assertContains(response, config2.device.name)

    def test_delete_device(self):
        self.config.device.deactivate()
        self.config.set_status_deactivated()
        device_response = self.client.post(
            reverse(
                f"admin:{self.config_label}_device_delete",
                args=[self.config.device_id],
            ),
            {"post": "yes"},
        )
        self.assertEqual(device_response.status_code, 302)
        self.assertEqual(Device.objects.count(), 0)
        self.assertEqual(self.subnet_query.exclude(id=self.master_subnet.id).count(), 0)

        subnet_response = self.client.get(
            reverse(f"admin:{self.ipam_label}_subnet_changelist")
        )
        self.assertEqual(subnet_response.status_code, 200)
        self.assertContains(subnet_response, self.config.device.name, 1)


class TestTransactionDeviceAdmin(
    SubnetDivisionTestMixin,
    TestVpnX509Mixin,
    TestDeviceAdminMixin,
    TransactionTestCase,
):
    ipam_label = "openwisp_ipam"
    config_label = "config"

    def test_vpn_template_switch_checksum_db(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        org = self._get_org()
        vpn1_subnet = self._get_master_subnet(organization=org, subnet="10.0.0.0/24")
        self._get_vpn_subdivision_rule(
            number_of_ips=1,
            number_of_subnets=1,
            organization=org,
            master_subnet=vpn1_subnet,
            label="VPN1",
        )
        vpn1 = self._create_vpn(name="vpn1", organization=org, subnet=vpn1_subnet)
        vpn2_subnet = self._get_master_subnet(organization=org, subnet="10.0.1.0/24")
        self._get_vpn_subdivision_rule(
            number_of_ips=1,
            number_of_subnets=1,
            organization=org,
            master_subnet=vpn2_subnet,
            label="VPN2",
        )
        vpn2 = self._create_vpn(name="vpn2", organization=org, subnet=vpn2_subnet)
        vpn1_template = self._create_template(
            organization=org,
            name="vpn1-template",
            type="vpn",
            vpn=vpn1,
            default_values={
                "VPN1_subnet1_ip1": "10.0.0.1",
                "VPN1_prefix": "24",
                "ifname": "tun0",
            },
            auto_cert=True,
            config={},
        )
        vpn1_template.config["openvpn"][0]["dev"] = "{{ ifname }}"
        vpn1_template.config.update(
            {
                "network": [
                    {
                        "config_name": "interface",
                        "config_value": "lan",
                        "ipaddr": "{{ VPN1_subnet1_ip1 }}",
                        "netmask": "255.255.255.240",
                    }
                ],
            }
        )
        vpn1_template.full_clean()
        vpn1_template.save()
        vpn2_template = self._create_template(
            organization=org,
            name="vpn2-template",
            type="vpn",
            vpn=vpn2,
            default_values={
                "VPN2_subnet1_ip1": "10.0.1.1",
                "VPN2_prefix": "32",
                "ifname": "tun1",
            },
            auto_cert=True,
            config={},
        )
        vpn2_template.config["openvpn"][0]["dev"] = "{{ ifname }}"
        vpn2_template.config.update(
            {
                "network": [
                    {
                        "config_name": "interface",
                        "config_value": "lan",
                        "ipaddr": "{{ VPN2_subnet1_ip1 }}",
                        "netmask": "255.255.255.240",
                    }
                ],
            }
        )
        vpn2_template.full_clean()
        vpn2_template.save()
        default_template = self._create_template(
            name="default-template",
            default=True,
        )
        path = reverse(f"admin:{self.config_label}_device_add")
        params = self._get_device_params(org=org)
        params.update(
            {"config-0-templates": f"{default_template.pk},{vpn1_template.pk}"}
        )
        response = self.client.post(path, data=params, follow=True)
        self.assertEqual(response.status_code, 200)
        config = Config.objects.get(device__name=params["name"])
        config.refresh_from_db()
        config._invalidate_backend_instance_cache()
        initial_checksum = config.checksum
        self.assertEqual(config.checksum_db, initial_checksum)
        self.assertEqual(config.vpnclient_set.count(), 1)
        self.assertEqual(config.vpnclient_set.first().vpn, vpn1)

        path = reverse(
            f"admin:{self.config_label}_device_change", args=[config.device_id]
        )
        params.update(
            {
                "config-0-templates": f"{default_template.pk},{vpn2_template.pk}",
                "config-0-id": str(config.pk),
                "config-0-device": str(config.device_id),
                "config-INITIAL_FORMS": 1,
                "_continue": True,
            }
        )
        response = self.client.post(path, data=params, follow=True)
        self.assertEqual(response.status_code, 200)
        config.refresh_from_db()
        config._invalidate_backend_instance_cache()
        self.assertEqual(config.status, "modified")
        self.assertEqual(config.vpnclient_set.count(), 1)
        self.assertEqual(config.vpnclient_set.first().vpn, vpn2)
        self.assertNotEqual(config.checksum, initial_checksum)
        self.assertEqual(config.checksum, config.checksum_db)

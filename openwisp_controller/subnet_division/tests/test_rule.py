from django.db import connection
from django.test import TestCase, tag
from openwisp_ipam.tests import CreateModelsMixin as SubnetIpamMixin
from swapper import load_model

from ..rule_types.base import BaseSubnetDivisionRuleType
from ..rule_types.vpn import VpnSubnetDivisionRuleType

SubnetDivisionRule = load_model('subnet_division', 'SubnetDivisionRule')


class TestBaseSubnetDivisionRuleType(SubnetIpamMixin, TestCase):
    def test_should_create_subnets_ips(self):
        with self.assertRaises(NotImplementedError):
            BaseSubnetDivisionRuleType.should_create_subnets_ips(instance=None)

    def test_provision_for_existing_objects(self):
        with self.assertRaises(NotImplementedError):
            BaseSubnetDivisionRuleType.provision_for_existing_objects(rule_obj=None)

    @tag('db_tests')
    def test_get_max_subnet(self):
        rule = SubnetDivisionRule(
            **{
                'label': 'OW',
                'size': 28,
                'number_of_ips': 2,
                'number_of_subnets': 2,
                'type': VpnSubnetDivisionRuleType,
            }
        )
        master_subnet = self._create_subnet(subnet='10.0.0.0/16')
        self._create_subnet(subnet='10.0.0.16/28', master_subnet=master_subnet)
        self._create_subnet(subnet='10.0.0.0/28', master_subnet=master_subnet)
        max_subnet = VpnSubnetDivisionRuleType.get_max_subnet(master_subnet, rule)
        if connection.vendor == 'postgresql':
            self.assertEqual(str(max_subnet), '10.0.0.16/28')
        else:
            self.assertEqual(str(max_subnet), '10.0.0.0/28')

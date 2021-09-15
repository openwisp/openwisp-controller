from django.test import TestCase

from ..rule_types.base import BaseSubnetDivisionRuleType


class TestBaseSubnetDivisionRuleType(TestCase):
    def test_should_create_subnets_ips(self):
        with self.assertRaises(NotImplementedError):
            BaseSubnetDivisionRuleType.should_create_subnets_ips(instance=None)

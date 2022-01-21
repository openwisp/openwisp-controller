from django.db import connections
from django.db.utils import DEFAULT_DB_ALIAS
from django.test.testcases import _AssertNumQueriesContext
from openwisp_ipam.tests import CreateModelsMixin as SubnetIpamMixin
from swapper import load_model

from openwisp_controller.subnet_division.rule_types.device import (
    DeviceSubnetDivisionRuleType,
)

from ...config.tests.utils import CreateConfigTemplateMixin, TestWireguardVpnMixin
from ..rule_types.vpn import VpnSubnetDivisionRuleType

SubnetDivisionRule = load_model('subnet_division', 'SubnetDivisionRule')
SubnetDivisionIndex = load_model('subnet_division', 'SubnetDivisionIndex')
Subnet = load_model('openwisp_ipam', 'Subnet')


class SubnetDivisionTestMixin(
    CreateConfigTemplateMixin, TestWireguardVpnMixin, SubnetIpamMixin
):
    @property
    def subnet_query(self):
        return Subnet.objects.exclude(name__contains='Reserved')

    def _create_subnet_division_rule(self, **kwargs):
        options = dict()
        options.update(self._get_extra_fields(**kwargs))
        options.update(kwargs)
        instance = SubnetDivisionRule(**options)
        instance.full_clean()
        instance.save()
        return instance

    def _get_subnet_division_rule(self, type, **kwargs):
        options = {
            'label': 'OW',
            'size': 28,
            'number_of_ips': 2,
            'number_of_subnets': 2,
            'type': type,
        }
        options.update(**kwargs)
        if 'master_subnet' not in kwargs:
            options['master_subnet'] = self._get_master_subnet()
        return self._create_subnet_division_rule(**options)

    def _get_vpn_subdivision_rule(self, **kwargs):
        path = (
            f'{VpnSubnetDivisionRuleType.__module__}.'
            f'{VpnSubnetDivisionRuleType.__name__}'
        )
        return self._get_subnet_division_rule(type=path, **kwargs)

    def _get_device_subdivision_rule(self, **kwargs):
        path = (
            f'{DeviceSubnetDivisionRuleType.__module__}.'
            f'{DeviceSubnetDivisionRuleType.__name__}'
        )
        return self._get_subnet_division_rule(type=path, **kwargs)

    def _get_master_subnet(self, subnet='10.0.0.0/16', **kwargs):
        try:
            return Subnet.objects.get(subnet=subnet, **kwargs)
        except Subnet.DoesNotExist:
            return self._create_subnet(subnet=subnet, **kwargs)


class _CustomAssertnumQueriesContext(_AssertNumQueriesContext):
    def __exit__(self, exc_type, exc_value, traceback):
        """
        This method increases the number of expected database
        queries if subnet_division app is enabled. Tests in
        "openwisp_controller.config" are written assuming
        subnet_division is disabled. Therefore, it is required
        to increase the number of expected queries in those tests.
        """
        if exc_type is not None:
            return
        for query in self.captured_queries:
            if 'subnetdivision' in query['sql']:
                self.num += 1
        super().__exit__(exc_type, exc_value, traceback)


def subnetdivision_patched_assertNumQueries(
    self, num, func=None, *args, using=DEFAULT_DB_ALIAS, **kwargs
):
    conn = connections[using]

    context = _CustomAssertnumQueriesContext(self, num, conn)
    if func is None:
        return context

    with context:
        func(*args, **kwargs)

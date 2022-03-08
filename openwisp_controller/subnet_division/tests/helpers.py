from django.db import connections
from django.db.utils import DEFAULT_DB_ALIAS
from django.test.testcases import _AssertNumQueriesContext
from netaddr import IPNetwork
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

    def _mock_subnet_division_rule(self, config, master_subnet, rule):
        """
        Imitates triggering of subnet division rule and provisions subnets.
        Useful when subnet division rules are not triggered due to
        working of django.test.TestCase class.
        """
        try:
            max_subnet = (
                # Get the highest subnet created for this master_subnet
                Subnet.objects.filter(master_subnet_id=master_subnet.id)
                .order_by('-created')
                .first()
                .subnet
            )
        except AttributeError:
            # If there is no existing subnet, create a reserved subnet
            # and use it as starting point
            required_subnet = next(
                IPNetwork(str(master_subnet.subnet)).subnet(prefixlen=32)
            )
        else:
            required_subnet = IPNetwork(str(max_subnet)).next()

        subnet = self._create_subnet(
            organization=config.device.organization,
            subnet=required_subnet,
            master_subnet=master_subnet,
            name='TEST_subnet1',
        )
        ip = subnet.request_ip()
        SubnetDivisionIndex.objects.create(
            rule=rule, config=config, subnet=subnet, keyword='TEST_subnet1'
        )
        SubnetDivisionIndex.objects.create(
            rule=rule,
            config=config,
            # subnet=subnet,
            ip=ip,
            keyword='TEST_subnet1_ip1',
        )


class SubnetDivisionAdminTestMixin(SubnetDivisionTestMixin):
    def setUp(self):
        org = self._get_org()
        self.master_subnet = self._get_master_subnet()
        self.config = self._create_config(organization=org)
        self.rule = self._get_vpn_subdivision_rule(number_of_ips=1, number_of_subnets=1)
        self._mock_subnet_division_rule(self.config, self.master_subnet, self.rule)
        admin = self._get_admin()
        self.client.force_login(admin)


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

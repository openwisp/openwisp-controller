from openwisp_ipam.tests import CreateModelsMixin as SubnetIpamMixin
from swapper import load_model

from openwisp_controller.subnet_division.rule_types.device import (
    DeviceSubnetDivisionRuleType,
)

from ...config.tests.utils import CreateConfigTemplateMixin, TestVpnX509Mixin
from ..rule_types.vpn import VpnSubnetDivisionRuleType

SubnetDivisionRule = load_model('subnet_division', 'SubnetDivisionRule')
SubnetDivisionIndex = load_model('subnet_division', 'SubnetDivisionIndex')
Subnet = load_model('openwisp_ipam', 'Subnet')


class SubnetDivisionTestMixin(
    CreateConfigTemplateMixin, TestVpnX509Mixin, SubnetIpamMixin
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

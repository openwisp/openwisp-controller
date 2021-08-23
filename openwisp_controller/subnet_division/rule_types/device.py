from django.db.models.signals import post_delete
from swapper import load_model

from ...config.signals import device_registered
from .base import BaseSubnetDivisionRuleType

Subnet = load_model('openwisp_ipam', 'Subnet')


class DeviceSubnetDivisionRuleType(BaseSubnetDivisionRuleType):
    provision_signal = device_registered
    provision_sender = ('config', 'Device')
    provision_dispatch_uid = 'device_registered_provision_subnet'

    destroyer_signal = post_delete
    destroyer_sender = ('config', 'Config')
    destroyer_dispatch_uid = 'device_registered_destroy_subnet'

    organization_id_path = 'organization_id'
    subnet_path = ''

    @classmethod
    def get_subnet(cls, instance):
        return instance.organization.subnetdivisionrule_set.get(
            type=f'{cls.__module__}.{cls.__name__}'
        ).master_subnet

    @classmethod
    def should_create_subnets_ips(cls, instance, **kwargs):
        return kwargs['is_new']

    @staticmethod
    def destroy_provisioned_subnets_ips(instance, **kwargs):
        # Deleting related subnets automatically deletes related IpAddress
        # and SubnetDivisionIndex objects
        subnet_ids = instance.subnetdivisionindex_set.values_list('subnet_id')
        Subnet.objects.filter(id__in=subnet_ids).delete()

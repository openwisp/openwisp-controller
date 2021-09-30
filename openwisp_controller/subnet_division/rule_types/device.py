from django.db.models.signals import post_delete, post_save
from swapper import load_model

from .base import BaseSubnetDivisionRuleType

Config = load_model('config', 'Config')
Subnet = load_model('openwisp_ipam', 'Subnet')


class DeviceSubnetDivisionRuleType(BaseSubnetDivisionRuleType):
    provision_signal = post_save
    provision_sender = ('config', 'Config')
    provision_dispatch_uid = 'device_registered_provision_subnet'

    destroyer_signal = post_delete
    destroyer_sender = ('config', 'Config')
    destroyer_dispatch_uid = 'device_registered_destroy_subnet'

    organization_id_path = 'device.organization_id'
    subnet_path = ''
    config_path = 'self'

    @classmethod
    def get_subnet(cls, instance):
        pass

    @classmethod
    def get_subnet_division_rules(cls, instance):
        rule_type = f'{cls.__module__}.{cls.__name__}'
        return instance.device.organization.subnetdivisionrule_set.filter(
            type=rule_type
        ).iterator()

    @classmethod
    def should_create_subnets_ips(cls, instance, **kwargs):
        return kwargs.get('created', False)

    @staticmethod
    def destroy_provisioned_subnets_ips(instance, **kwargs):
        # Deleting related subnets automatically deletes related IpAddress
        # and SubnetDivisionIndex objects
        subnet_ids = instance.subnetdivisionindex_set.values_list('subnet_id')
        Subnet.objects.filter(id__in=subnet_ids).delete()

    @classmethod
    def provision_for_existing_objects(cls, rule_obj):
        for config in (
            Config.objects.select_related('device', 'device__organization')
            .filter(device__organization_id=rule_obj.organization_id)
            .iterator()
        ):
            cls.provision_receiver(config, created=True, rule=rule_obj)

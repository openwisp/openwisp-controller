from django.db.models.signals import post_delete, post_save

from .base import BaseSubnetDivisionRuleType


class VpnSubnetDivisionRuleType(BaseSubnetDivisionRuleType):
    provision_signal = post_save
    provision_sender = ('config', 'VpnClient')
    provision_dispatch_uid = 'vpn_client_provision_subnet'

    destroyer_signal = post_delete
    destroyer_sender = provision_sender
    destroyer_dispatch_uid = 'vpn_client_destroy_subnet'

    organization_id_path = 'config.device.organization_id'
    subnet_path = 'vpn.subnet'

    @classmethod
    def should_create_subnets_ips(cls, instance, **kwargs):
        return kwargs['created']

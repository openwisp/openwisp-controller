from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from swapper import load_model

from .base import BaseSubnetDivisionRuleType

Vpn = load_model('config', 'Vpn')
VpnClient = load_model('config', 'VpnClient')


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
        return kwargs.get('created', False)

    @classmethod
    def provision_for_existing_objects(cls, rule_obj):
        organization_filter = Q(organization_id=rule_obj.organization_id) | Q(
            organization_id=None
        )
        vpn_qs = (
            Vpn.objects.filter(subnet=rule_obj.master_subnet)
            .filter(organization_filter)
            .values_list('id')
        )
        qs = VpnClient.objects.filter(
            vpn__in=vpn_qs, config__device__organization_id=rule_obj.organization_id
        )
        for vpn_client in qs:
            cls.provision_receiver(instance=vpn_client, created=True)

    @staticmethod
    def post_provision_handler(instance, provisioned, **kwargs):
        # Assign the first provisioned IP address to the VPNClient
        # only when subnets and IPs have been provisioned
        if provisioned and provisioned['ip_addresses']:
            # Delete any previously assigned IP address
            if instance.ip:
                instance.ip.delete()
            instance.ip = provisioned['ip_addresses'][0]
            instance.full_clean()
            instance.save()

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from swapper import load_model

logger = logging.getLogger(__name__)

Subnet = load_model('openwisp_ipam', 'Subnet')
IpAddress = load_model('openwisp_ipam', 'IpAddress')
SubnetDivisionRule = load_model('subnet_division', 'SubnetDivisionRule')
SubnetDivisionIndex = load_model('subnet_division', 'SubnetDivisionIndex')
VpnClient = load_model('config', 'VpnClient')


@receiver(
    pre_save,
    sender=SubnetDivisionRule,
    dispatch_uid='subnet_division_rule_changed_fields',
)
def subnet_division_rule_changed_fields(instance, **kwargs):
    instance.check_and_queue_modified_fields()


@receiver(
    post_save,
    sender=SubnetDivisionRule,
    dispatch_uid='update_subnet_division_rule_related',
)
def update_subnet_division_rule_related(instance, created, **kwargs):
    if created:
        return

    transaction.on_commit(instance.update_related_objects)


@receiver(
    post_delete, sender=SubnetDivisionRule, dispatch_uid='delete_provisioned_subnets'
)
def delete_provisioned_subnets(instance, **kwargs):
    transaction.on_commit(instance.delete_provisioned_subnets)

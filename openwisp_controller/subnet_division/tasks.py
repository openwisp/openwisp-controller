import logging

from celery import shared_task
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from swapper import load_model

logger = logging.getLogger(__name__)

Subnet = load_model('openwisp_ipam', 'Subnet')
IpAddress = load_model('openwisp_ipam', 'IpAddress')
SubnetDivisionRule = load_model('subnet_division', 'SubnetDivisionRule')
SubnetDivisionIndex = load_model('subnet_division', 'SubnetDivisionIndex')


@shared_task
def update_subnet_division_index(rule_id):
    try:
        division_rule = SubnetDivisionRule.objects.get(id=rule_id)
    except SubnetDivisionRule.DoesNotExist as e:
        logger.warning(
            'Failed to update indexes for Subnet Division Rule '
            f'with id: "{rule_id}", reason: {e}'
        )
        return

    index_queryset = division_rule.subnetdivisionindex_set.all()
    for index in index_queryset:
        identifiers = index.keyword.split('_')
        identifiers[0] = division_rule.label
        index.keyword = '_'.join(identifiers)

    SubnetDivisionIndex.objects.bulk_update(
        index_queryset, fields=['keyword'], batch_size=20
    )


@shared_task
def update_subnet_name_description(rule_id):
    try:
        division_rule = SubnetDivisionRule.objects.get(id=rule_id)
    except SubnetDivisionRule.DoesNotExist as e:
        logger.warning(
            'Failed to update subnets related to Subnet Division Rule '
            f'with id: "{rule_id}", reason: {e}'
        )
        return

    related_subnet_ids = division_rule.subnetdivisionindex_set.filter(
        subnet_id__isnull=False, ip_id__isnull=True,
    ).values_list('subnet_id')
    subnet_queryset = Subnet.objects.filter(id__in=related_subnet_ids)

    for subnet in subnet_queryset:
        identifiers = subnet.name.split('_')
        identifiers[0] = division_rule.label
        subnet.name = '_'.join(identifiers)
        subnet.description = _(
            f'Automatically generated using {division_rule.label} rule.'
        )

    Subnet.objects.bulk_update(
        subnet_queryset, fields=['name', 'description'], batch_size=20
    )


@shared_task
def provision_extra_ips(rule_id, old_number_of_ips):
    def _create_ipaddress_and_subnetdivision_index_objects(ips, indexes):
        IpAddress.objects.bulk_create(ips)
        SubnetDivisionIndex.objects.bulk_create(indexes)

    generated_ips = []
    generated_indexes = []

    try:
        division_rule = SubnetDivisionRule.objects.get(id=rule_id)
    except SubnetDivisionRule.DoesNotExist as e:
        logger.warning(
            'Failed to provision extra IPs for Subnet Division Rule '
            f'with id: "{rule_id}", reason: {e}'
        )
        return

    index_queryset = division_rule.subnetdivisionindex_set.filter(
        subnet_id__isnull=False, config_id__isnull=False, ip_id__isnull=True,
    ).select_related('subnet')

    starting_ip_id = old_number_of_ips + 1
    ending_ip_id = division_rule.number_of_ips + 1

    for index in index_queryset:
        subnet = index.subnet
        for ip_id in range(starting_ip_id, ending_ip_id):
            ip = IpAddress(subnet_id=subnet.id, ip_address=str(subnet.subnet[ip_id]),)

            generated_ips.append(ip)
            generated_indexes.append(
                SubnetDivisionIndex(
                    keyword=f'{division_rule.label}_subnet{subnet.id}_ip{ip_id}',
                    subnet_id=subnet.id,
                    ip_id=ip.id,
                    rule_id=division_rule.id,
                    config_id=index.config_id,
                )
            )

    transaction.on_commit(
        lambda: _create_ipaddress_and_subnetdivision_index_objects(
            generated_ips, generated_indexes
        )
    )

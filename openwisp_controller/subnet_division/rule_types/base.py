import logging
from ipaddress import ip_network
from operator import attrgetter

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.dispatch import Signal
from django.utils.translation import ugettext_lazy as _
from netaddr import IPNetwork
from swapper import load_model

logger = logging.getLogger(__name__)

Subnet = load_model('openwisp_ipam', 'Subnet')
IpAddress = load_model('openwisp_ipam', 'IpAddress')
SubnetDivisionRule = load_model('subnet_division', 'SubnetDivisionRule')
SubnetDivisionIndex = load_model('subnet_division', 'SubnetDivisionIndex')
VpnClient = load_model('config', 'VpnClient')


class BaseSubnetDivisionRuleType(object):
    provision_signal = None
    provision_sender = None
    provision_dispatch_uid = None

    destroyer_signal = None
    destroyer_sender = None
    destroyer_dispatch_uid = None

    organization_id_path = None
    subnet_path = None

    @classmethod
    def validate_rule_type(cls):
        assert issubclass(cls, BaseSubnetDivisionRuleType)

        assert isinstance(cls.provision_signal, Signal)
        assert isinstance(cls.provision_dispatch_uid, str)
        cls.provision_sender = load_model(*cls.provision_sender)

        assert isinstance(cls.destroyer_signal, Signal)
        assert isinstance(cls.destroyer_dispatch_uid, str)
        cls.destroyer_sender = load_model(*cls.destroyer_sender)

        assert isinstance(cls.organization_id_path, str)
        assert isinstance(cls.subnet_path, str)

    @classmethod
    def provision_receiver(cls, instance, **kwargs):
        rule_type = f'{cls.__module__}.{cls.__name__}'
        transaction.on_commit(
            lambda: cls.create_subnets_ips(instance, rule_type, **kwargs)
        )

    @classmethod
    def destroyer_receiver(cls, instance, **kwargs):
        cls.destroy_provisioned_subnets_ips(instance, **kwargs)

    @classmethod
    def create_subnets_ips(cls, instance, rule_type, **kwargs):
        if not kwargs['created']:
            return

        try:
            organization_id = cls.get_organization(instance)
            subnet = cls.get_subnet(instance)
            division_rule = subnet.subnetdivisionrule_set.get(
                organization_id__in=(organization_id, None), type=rule_type,
            )
        except (AttributeError, ObjectDoesNotExist):
            return

        master_subnet = division_rule.master_subnet
        max_subnet = cls.get_max_subnet(master_subnet)
        generated_indexes = []
        generated_subnets = cls.create_subnets(
            instance, division_rule, max_subnet, generated_indexes
        )
        cls.create_ips(instance, division_rule, generated_subnets, generated_indexes)
        SubnetDivisionIndex.objects.bulk_create(generated_indexes)

    @classmethod
    def get_organization(cls, instance):
        return attrgetter(cls.organization_id_path)(instance)

    @classmethod
    def get_subnet(cls, instance):
        return attrgetter(cls.subnet_path)(instance)

    @staticmethod
    def get_max_subnet(master_subnet):
        try:
            max_subnet = (
                # Get the highest subnet created for this master_subnet
                SubnetDivisionIndex.objects.select_related(
                    'subnet', 'subnet__master_subnet'
                )
                .filter(subnet__master_subnet_id=master_subnet.id)
                .order_by('-subnet__created')
                .first()
                .subnet
            )
        except AttributeError:
            max_subnet = None
        finally:
            return max_subnet

    @staticmethod
    def create_subnets(instance, division_rule, max_subnet, generated_indexes):
        master_subnet = division_rule.master_subnet
        if max_subnet is None:
            required_subnet = next(
                IPNetwork(str(master_subnet.subnet)).subnet(
                    prefixlen=division_rule.size
                )
            )
        else:
            required_subnet = IPNetwork(str(max_subnet.subnet)).next()

        generated_subnets = []

        for subnet_id in range(1, division_rule.number_of_subnets + 1):
            if not ip_network(str(required_subnet)).subnet_of(master_subnet.subnet):
                logger.error(f'Cannot create more subnets of {master_subnet}')
                break
            subnet_obj = Subnet(
                name=f'{division_rule.label}_subnet{subnet_id}',
                subnet=str(required_subnet),
                description=_(
                    f'Automatically generated using {division_rule.label} rule.'
                ),
                master_subnet_id=master_subnet.id,
                organization_id=division_rule.organization_id,
            )
            subnet_obj.full_clean()
            generated_subnets.append(subnet_obj)
            generated_indexes.append(
                SubnetDivisionIndex(
                    keyword=f'{division_rule.label}_subnet{subnet_id}',
                    subnet_id=subnet_obj.id,
                    rule_id=division_rule.id,
                    config_id=instance.config_id,
                )
            )
            required_subnet = required_subnet.next()
        Subnet.objects.bulk_create(generated_subnets)
        return generated_subnets

    @staticmethod
    def create_ips(instance, division_rule, generated_subnets, generated_indexes):
        generated_ips = []
        for subnet_obj in generated_subnets:
            for ip_id in range(1, division_rule.number_of_ips + 1):
                ip_obj = IpAddress(
                    subnet_id=subnet_obj.id, ip_address=str(subnet_obj.subnet[ip_id]),
                )
                ip_obj.full_clean()
                generated_ips.append(ip_obj)

                generated_indexes.append(
                    SubnetDivisionIndex(
                        keyword=f'{subnet_obj.name}_ip{ip_id}',
                        subnet_id=subnet_obj.id,
                        ip_id=ip_obj.id,
                        rule_id=division_rule.id,
                        config_id=instance.config_id,
                    )
                )

        IpAddress.objects.bulk_create(generated_ips)

    @staticmethod
    def destroy_provisioned_subnets_ips(instance, **kwargs):
        # Deleting related subnets automatically deletes related IpAddress
        # and SubnetDivisionIndex objects
        subnet_ids = instance.config.subnetdivisionindex_set.values_list('subnet_id')
        Subnet.objects.filter(id__in=subnet_ids).delete()

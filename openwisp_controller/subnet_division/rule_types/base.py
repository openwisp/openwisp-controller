import logging
from ipaddress import ip_network
from operator import attrgetter

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.dispatch import Signal
from django.utils.translation import gettext_lazy as _
from netaddr import IPNetwork
from swapper import load_model

from ..signals import subnet_provisioned

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
    config_path = 'config'

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
        def _provision_receiver():
            # If any of following operations fail, the database transaction
            # should fail/rollback.

            # This method is also called by "provision_for_existing_objects"
            # which passes the "rule" keyword argument. In such case,
            # provisioning should be only triggered for received rule.
            if 'rule' in kwargs:
                rules = [kwargs['rule']]
            else:
                try:
                    rules = cls.get_subnet_division_rules(instance)
                except (AttributeError, ObjectDoesNotExist):
                    return
            for rule in rules:
                provisioned = cls.create_subnets_ips(instance, rule, **kwargs)
                cls.post_provision_handler(instance, provisioned, **kwargs)
                cls.subnet_provisioned_signal_emitter(instance, provisioned)

        if not cls.should_create_subnets_ips(instance, **kwargs):
            return

        transaction.on_commit(_provision_receiver)

    @classmethod
    def destroyer_receiver(cls, instance, **kwargs):
        cls.destroy_provisioned_subnets_ips(instance, **kwargs)

    @staticmethod
    def post_provision_handler(instance, provisioned, **kwargs):
        """
        This method should be overridden in inherited rule types to
        perform any operation on provisioned subnets and IP addresses.
        :param instance: object that triggered provisioning
        :param provisioned: dictionary containing subnets and IP addresses
            provisioned, None if nothing is provisioned
        """
        pass

    @staticmethod
    def subnet_provisioned_signal_emitter(instance, provisioned):
        subnet_provisioned.send(
            sender=SubnetDivisionRule, instance=instance, provisioned=provisioned
        )

    @classmethod
    def should_create_subnets_ips(cls, instance, **kwargs):
        """
        return a boolean value whether subnets and IPs should
        be provisioned for "instance" object
        """
        raise NotImplementedError()

    @classmethod
    def provision_for_existing_objects(cls, rule_obj):
        """
        Contains logic to trigger provisioning for existing objects
        """
        raise NotImplementedError()

    @classmethod
    def create_subnets_ips(cls, instance, division_rule, **kwargs):
        try:
            config = cls.get_config(instance)
        except (AttributeError, ObjectDoesNotExist):
            return

        master_subnet = division_rule.master_subnet
        max_subnet = cls.get_max_subnet(master_subnet, division_rule)
        generated_indexes = []
        generated_subnets = cls.create_subnets(
            config, division_rule, max_subnet, generated_indexes
        )
        generated_ips = cls.create_ips(
            config, division_rule, generated_subnets, generated_indexes
        )
        SubnetDivisionIndex.objects.bulk_create(generated_indexes)
        return {'subnets': generated_subnets, 'ip_addresses': generated_ips}

    @classmethod
    def get_organization(cls, instance):
        return attrgetter(cls.organization_id_path)(instance)

    @classmethod
    def get_subnet(cls, instance):
        return attrgetter(cls.subnet_path)(instance)

    @classmethod
    def get_subnet_division_rules(cls, instance):
        rule_type = f'{cls.__module__}.{cls.__name__}'
        organization_id = cls.get_organization(instance)
        subnet = cls.get_subnet(instance)
        return subnet.subnetdivisionrule_set.filter(
            organization_id__in=(organization_id, None),
            type=rule_type,
        ).iterator()

    @classmethod
    def get_config(cls, instance):
        if cls.config_path == 'self':
            return instance
        else:
            return attrgetter(cls.config_path)(instance)

    @staticmethod
    def get_max_subnet(master_subnet, division_rule):
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
                IPNetwork(str(master_subnet.subnet)).subnet(
                    prefixlen=division_rule.size
                )
            )
            subnet_obj = Subnet(
                name=f'Reserved Subnet {required_subnet}',
                subnet=str(required_subnet),
                description=_('Automatically generated reserved subnet.'),
                master_subnet_id=master_subnet.id,
                organization_id=master_subnet.organization_id,
            )
            subnet_obj.full_clean()
            subnet_obj.save()
            max_subnet = subnet_obj.subnet
        finally:
            return max_subnet

    @staticmethod
    def create_subnets(config, division_rule, max_subnet, generated_indexes):
        master_subnet = division_rule.master_subnet
        required_subnet = IPNetwork(str(max_subnet)).next()
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
                    config=config,
                )
            )
            required_subnet = required_subnet.next()
        Subnet.objects.bulk_create(generated_subnets)
        return generated_subnets

    @staticmethod
    def create_ips(config, division_rule, generated_subnets, generated_indexes):
        generated_ips = []
        for subnet_obj in generated_subnets:
            for ip_id in range(1, division_rule.number_of_ips + 1):
                ip_obj = IpAddress(
                    subnet_id=subnet_obj.id,
                    ip_address=str(subnet_obj.subnet[ip_id]),
                )
                ip_obj.full_clean()
                generated_ips.append(ip_obj)

                generated_indexes.append(
                    SubnetDivisionIndex(
                        keyword=f'{subnet_obj.name}_ip{ip_id}',
                        subnet_id=subnet_obj.id,
                        ip_id=ip_obj.id,
                        rule_id=division_rule.id,
                        config=config,
                    )
                )

        IpAddress.objects.bulk_create(generated_ips)
        return generated_ips

    @classmethod
    def destroy_provisioned_subnets_ips(cls, instance, **kwargs):
        # Deleting related subnets automatically deletes related IpAddress
        # and SubnetDivisionIndex objects
        config = cls.get_config(instance)
        rule_type = f'{cls.__module__}.{cls.__name__}'
        subnet_ids = config.subnetdivisionindex_set.filter(
            rule__type=rule_type
        ).values_list('subnet_id')
        Subnet.objects.filter(id__in=subnet_ids).delete()

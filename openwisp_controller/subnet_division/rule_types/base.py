import logging
from ipaddress import ip_network
from operator import attrgetter
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.dispatch import Signal
from django.utils.translation import gettext_lazy as _
from netaddr import IPNetwork, IPSet
from openwisp_notifications.signals import notify
from swapper import load_model
from ..signals import subnet_provisioned

logger = logging.getLogger(__name__)
Subnet = load_model("openwisp_ipam", "Subnet")
IpAddress = load_model("openwisp_ipam", "IpAddress")
SubnetDivisionRule = load_model("subnet_division", "SubnetDivisionRule")
SubnetDivisionIndex = load_model("subnet_division", "SubnetDivisionIndex")


class BaseSubnetDivisionRuleType(object):
    provision_signal = provision_sender = provision_dispatch_uid = None
    destroyer_signal = destroyer_sender = destroyer_dispatch_uid = None
    organization_id_path = subnet_path = None
    config_path = "config"

    @classmethod
    def validate_rule_type(cls):
        assert issubclass(cls, BaseSubnetDivisionRuleType)
        assert isinstance(cls.provision_signal, Signal)
        cls.provision_sender = load_model(*cls.provision_sender)
        cls.destroyer_sender = load_model(*cls.destroyer_sender)

    @classmethod
    def provision_receiver(cls, instance, **kwargs):
        def _provision_receiver():
            try:
                rules = (
                    [kwargs["rule"]]
                    if "rule" in kwargs
                    else cls.get_subnet_division_rules(instance)
                )
            except (AttributeError, ObjectDoesNotExist):
                return
            for rule in rules:
                provisioned = cls.create_subnets_ips(instance, rule, **kwargs)
                cls.post_provision_handler(instance, provisioned, **kwargs)
                cls.subnet_provisioned_signal_emitter(instance, provisioned)

        if cls.should_create_subnets_ips(instance, **kwargs):
            transaction.on_commit(_provision_receiver)

    @classmethod
    def destroyer_receiver(cls, instance, **kwargs):
        cls.destroy_provisioned_subnets_ips(instance, **kwargs)

    @staticmethod
    def post_provision_handler(instance, provisioned, **kwargs):
        pass

    @staticmethod
    def subnet_provisioned_signal_emitter(instance, provisioned):
        subnet_provisioned.send(
            sender=SubnetDivisionRule, instance=instance, provisioned=provisioned
        )

    @classmethod
    def should_create_subnets_ips(cls, instance, **kwargs):
        raise NotImplementedError()

    @classmethod
    def provision_for_existing_objects(cls, rule_obj):
        raise NotImplementedError()

    @classmethod
    def get_organization(cls, instance):
        return attrgetter(cls.organization_id_path)(instance)

    @classmethod
    def get_subnet(cls, instance):
        return attrgetter(cls.subnet_path)(instance)

    @classmethod
    def get_config(cls, instance):
        p = cls.config_path or "config"
        conf = instance if p == "self" else attrgetter(p)(instance)
        if not conf._meta.model.objects.filter(pk=conf.pk).exists():
            raise ObjectDoesNotExist()
        return conf

    @classmethod
    def get_subnet_division_rules(cls, instance):
        rt = f"{cls.__module__}.{cls.__name__}"
        org_id, subnet = cls.get_organization(instance), cls.get_subnet(instance)
        return subnet.subnetdivisionrule_set.filter(
            organization_id__in=(org_id, None), type=rt
        ).iterator()

    @staticmethod
    def get_max_subnet(ms, rule):
        qs = Subnet.objects.filter(master_subnet_id=ms.id)
        rule_nets = list(
            qs.filter(subnetdivisionindex__rule=rule).values_list("subnet", flat=True)
        )
        if not rule_nets:
            m_net = IPNetwork(str(ms.subnet))
            anchor = next(m_net.subnet(prefixlen=rule.size))
            obj, created = Subnet.objects.get_or_create(
                subnet=str(anchor),
                master_subnet_id=ms.id,
                defaults={
                    "name": f"Reserved Subnet {anchor}",
                    "description": _("Anchor point to protect address."),
                    "organization_id": ms.organization_id,
                },
            )
            return str(obj.subnet)
        parsed = [ip_network(str(s)) for s in rule_nets]
        return str(max(parsed, key=lambda n: int(n.network_address)))

    @staticmethod
    def create_subnets(config, rule, max_s, idxs):
        ms = rule.master_subnet
        exist = (
            Subnet.objects.filter(
                master_subnet_id=ms.id,
                subnetdivisionindex__rule=rule,
                subnetdivisionindex__config=config,
            )
            .values("id")
            .distinct()
            .count()
        )
        if exist >= rule.number_of_subnets:
            return []
        req = IPNetwork(str(max_s))
        a_qs = Subnet.objects.filter(subnet=max_s, master_subnet=ms)
        if exist > 0 or (a_qs.exists() and "Reserved" in (a_qs.first().name or "")):
            req = req.next()
        subs, space = [], IPSet(
            [str(s.subnet) for s in Subnet.objects.filter(master_subnet_id=ms.id)]
        )
        for s_id in range(exist + 1, rule.number_of_subnets + 1):
            while ip_network(str(req)).subnet_of(ms.subnet) and space.intersection(
                IPSet([req])
            ):
                req = req.next()
            if not ip_network(str(req)).subnet_of(ms.subnet):
                notify.send(
                    sender=config,
                    type="generic_message",
                    target=config.device,
                    level="error",
                    action_object=ms,
                    message=_(
                        "Failed to provision subnets for "
                        "[{notification.target}]({notification.target_link})"
                    ),
                    description=_(
                        "The [{notification.action_object}]"
                        "({notification.action_link}) subnet has run "
                        "out of space."
                    ),
                )
                logger.info(f"Cannot create more subnets of {ms.name} {ms.subnet}")
                break
            obj = Subnet.objects.create(
                name=f"{rule.label}_subnet{s_id}",
                subnet=str(req),
                description=_("Automatically provisioned subnet."),
                master_subnet_id=ms.id,
                organization_id=rule.organization_id,
            )
            subs.append(obj)
            space.update(IPSet([req]))
            idxs.append(
                SubnetDivisionIndex(
                    keyword=f"{rule.label}_subnet{s_id}",
                    subnet_id=obj.id,
                    rule_id=rule.id,
                    config=config,
                )
            )
        return subs

    @staticmethod
    def create_ips(config, rule, subnets, idxs):
        all_ips = []
        for s_obj in subnets:
            net = IPNetwork(str(s_obj.subnet))
            is_full = rule.number_of_ips >= len(net)
            start = 0 if (net.prefixlen in [32, 128] or is_full) else 1
            count = 0
            for ip_index in range(start, len(net)):
                if count >= rule.number_of_ips:
                    break
                addr = str(net[ip_index])
                obj = IpAddress.objects.create(subnet_id=s_obj.id, ip_address=addr)
                all_ips.append(obj)
                count += 1
                idxs.append(
                    SubnetDivisionIndex(
                        keyword=f"{s_obj.name}_ip{count}",
                        subnet_id=s_obj.id,
                        ip_id=obj.id,
                        rule_id=rule.id,
                        config=config,
                    )
                )
        return all_ips

    @classmethod
    def create_subnets_ips(cls, instance, division_rule, **kwargs):
        try:
            config = cls.get_config(instance)
        except (AttributeError, ObjectDoesNotExist):
            return
        with transaction.atomic():
            ms = division_rule.master_subnet
            max_s = cls.get_max_subnet(ms, division_rule)
            idxs = []
            subs = cls.create_subnets(config, division_rule, max_s, idxs)
            ips = cls.create_ips(config, division_rule, subs, idxs)
            SubnetDivisionIndex.objects.bulk_create(idxs)
            return {"subnets": subs, "ip_addresses": ips}

    @classmethod
    def destroy_provisioned_subnets_ips(cls, instance, **kwargs):
        config = cls.get_config(instance)
        rt = f"{cls.__module__}.{cls.__name__}"
        s_ids = config.subnetdivisionindex_set.filter(rule__type=rt).values_list(
            "subnet_id", flat=True
        )
        Subnet.objects.filter(id__in=s_ids).delete()

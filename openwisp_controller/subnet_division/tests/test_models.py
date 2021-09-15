import uuid
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from swapper import load_model

from .. import tasks
from .helpers import SubnetDivisionTestMixin

Subnet = load_model('openwisp_ipam', 'Subnet')
IpAddress = load_model('openwisp_ipam', 'IpAddress')
SubnetDivisionRule = load_model('subnet_division', 'SubnetDivisionRule')
SubnetDivisionIndex = load_model('subnet_division', 'SubnetDivisionIndex')
VpnClient = load_model('config', 'VpnClient')
Device = load_model('config', 'Device')


class TestSubnetDivisionRule(
    SubnetDivisionTestMixin, TransactionTestCase,
):
    def setUp(self):
        self.org = self._get_org()
        self.master_subnet = self._get_master_subnet()
        self.vpn_server = self._create_vpn(
            subnet=self.master_subnet, organization=self.org
        )
        self.template = self._create_template(
            name='vpn-test', type='vpn', vpn=self.vpn_server, organization=self.org
        )
        self.config = self._create_config(organization=self.org)

    def test_field_validations(self):
        default_options = {
            'label': 'OW',
            'size': 28,
            'master_subnet': self.master_subnet,
            'number_of_ips': 2,
            'number_of_subnets': 2,
            'type': (
                'openwisp_controller.subnet_division.rule_types.'
                'vpn.VpnSubnetDivisionRuleType'
            ),
            'organization': self.org,
        }

        with self.subTest('Test valid parameters'):
            options = default_options.copy()
            rule = SubnetDivisionRule(**options)
            rule.full_clean()
            self.assertEqual(str(rule), options['label'])

        with self.subTest('Test rule size exceeds size of master_subnet'):
            options = default_options.copy()
            options['size'] = 8
            rule = SubnetDivisionRule(**options)
            with self.assertRaises(ValidationError):
                rule.full_clean()

        with self.subTest('Test master_subnet cannot accommodate number_of_subnets'):
            options = default_options.copy()
            options['number_of_subnets'] = 99999999
            rule = SubnetDivisionRule(**options)
            with self.assertRaises(ValidationError):
                rule.full_clean()

        with self.subTest('Test generated subnets cannot accommodate number_of_ips'):
            options = default_options.copy()
            options['number_of_ips'] = 99999999
            rule = SubnetDivisionRule(**options)
            with self.assertRaises(ValidationError):
                rule.full_clean()

    def test_provisioned_subnets(self):
        rule = self._get_vpn_subdivision_rule()
        subnet_query = Subnet.objects.filter(organization_id=self.org.id).exclude(
            id=self.master_subnet.id
        )
        self.assertEqual(subnet_query.count(), 0)

        self.config.templates.add(self.template)

        self.assertEqual(
            subnet_query.count(), rule.number_of_subnets,
        )
        self.assertEqual(
            IpAddress.objects.count(), (rule.number_of_subnets * rule.number_of_ips)
        )

        # Verify context of config
        context = self.config.get_subnet_division_context()
        self.assertIn(f'{rule.label}_prefixlen', context)
        for subnet_id in range(1, rule.number_of_subnets + 1):
            self.assertIn(f'{rule.label}_subnet{subnet_id}', context)
            for ip_id in range(1, rule.number_of_ips + 1):
                self.assertIn(f'{rule.label}_subnet{subnet_id}_ip{ip_id}', context)

    def test_rule_label_updated(self):
        new_rule_label = 'TSDR'
        rule = self._get_vpn_subdivision_rule()
        self.config.templates.add(self.template)
        index_queryset = rule.subnetdivisionindex_set.filter(config_id=self.config.id)
        subnet_queryset = Subnet.objects.filter(
            id__in=index_queryset.filter(
                ip__isnull=True, subnet__isnull=False
            ).values_list('subnet_id', flat=True)
        )
        index_count = index_queryset.count()
        subnet_count = subnet_queryset.count()
        rule.label = 'TSDR'
        rule.save()
        rule.refresh_from_db()

        self.assertEqual(rule.label, new_rule_label)

        # Assert keywords of SubnetDivisionIndex are updated
        new_index_count = index_queryset.filter(
            keyword__startswith=new_rule_label,
        ).count()
        self.assertEqual(index_count, new_index_count)

        # Assert name and description of Subnet are updated
        new_subnet_count = subnet_queryset.filter(
            name__startswith=new_rule_label, description__contains=new_rule_label,
        ).count()
        self.assertEqual(subnet_count, new_subnet_count)

    def test_number_of_ips_updated(self):
        rule = self._get_vpn_subdivision_rule()
        self.config.templates.add(self.template)
        index_queryset = rule.subnetdivisionindex_set.filter(
            config_id=self.config.id, subnet_id__isnull=False, ip_id__isnull=False
        )

        # Check if nothing changes
        rule.save()
        rule.refresh_from_db()
        self.assertEqual(
            index_queryset.count(), rule.number_of_ips * rule.number_of_subnets
        )

        new_number_of_ips = rule.number_of_ips + 2
        rule.number_of_ips = new_number_of_ips
        rule.save()
        rule.refresh_from_db()

        self.assertEqual(rule.number_of_ips, new_number_of_ips)
        self.assertEqual(
            index_queryset.count(), new_number_of_ips * rule.number_of_subnets
        )

    def test_rule_deleted(self):
        rule = self._get_vpn_subdivision_rule()
        self.config.templates.add(self.template)
        subnet_query = Subnet.objects.exclude(id=self.master_subnet.id).filter(
            organization=rule.organization
        )
        ip_query = IpAddress.objects
        index_query = rule.subnetdivisionindex_set

        self.assertEqual(subnet_query.count(), rule.number_of_subnets)
        self.assertEqual(ip_query.count(), rule.number_of_subnets * rule.number_of_ips)
        self.assertEqual(
            index_query.count(),
            # Keywords for subnets + Keywords for IPs
            rule.number_of_subnets + (rule.number_of_subnets * rule.number_of_ips),
        )

        rule.delete()

        self.assertEqual(subnet_query.count(), 0)
        self.assertEqual(ip_query.count(), 0)
        self.assertEqual(index_query.count(), 0)

    def test_vpnclient_deleted(self):
        rule = self._get_vpn_subdivision_rule()
        self.config.templates.add(self.template)
        subnet_query = Subnet.objects.filter(organization_id=self.org.id).exclude(
            id=self.master_subnet.id
        )

        self.config.templates.add(self.template)

        self.assertEqual(
            subnet_query.count(), rule.number_of_subnets,
        )
        self.assertEqual(
            IpAddress.objects.count(), (rule.number_of_subnets * rule.number_of_ips)
        )

        self.config.templates.remove(self.template)
        self.assertEqual(
            subnet_query.count(), 0,
        )
        self.assertEqual(IpAddress.objects.count(), 0)

    @patch('logging.Logger.error')
    def test_subnets_exhausted(self, mocked_logger):
        subnet = self._get_master_subnet(
            '10.0.0.0/28', master_subnet=self.master_subnet
        )
        self._get_vpn_subdivision_rule(
            master_subnet=subnet, size=29,
        )
        self.vpn_server.subnet = subnet
        self.vpn_server.save()
        self.config.templates.add(self.template)

        config2 = self._create_config(
            device=self._create_device(mac_address='00:11:22:33:44:66')
        )
        config2.templates.add(self.template)
        mocked_logger.assert_called_with(f'Cannot create more subnets of {subnet}')

    def test_vpn_subnet_none(self):
        self.vpn_server.subnet = None
        self.vpn_server.save()

        rule = self._get_vpn_subdivision_rule()

        self.assertEqual(rule.subnetdivisionindex_set.count(), 0)
        self.assertEqual(Subnet.objects.exclude(id=self.master_subnet.id).count(), 0)
        self.assertEqual(IpAddress.objects.count(), 0)

    def test_vpn_subnet_no_rule(self):
        # Tests the scenario where a SubDivisionRule does not exist
        # for subnet of the VPN Server.
        self.config.templates.add(self.template)

    def test_subnet_already_provisioned(self):
        rule = self._get_vpn_subdivision_rule()
        index_count = (
            rule.number_of_subnets + rule.number_of_subnets * rule.number_of_ips
        )
        self.config.templates.add(self.template)
        self.assertEqual(
            self.config.subnetdivisionindex_set.count(), index_count,
        )
        vpn_client = VpnClient.objects.first()
        vpn_client.save()
        self.assertEqual(
            self.config.subnetdivisionindex_set.count(), index_count,
        )

    def test_shareable_vpn_vpnclient_subnet(self):
        self.vpn_server.organization = None
        self.vpn_server.save()

        self.template.organization = None
        self.template.save()

        self.master_subnet.organization = None
        self.master_subnet.save()

        rule = self._get_vpn_subdivision_rule()
        self.config.templates.add(self.template)

        # Following query asserts that subnet created belongs to the
        # organization of the related config.device
        subnet_query = Subnet.objects.filter(
            organization_id=self.org.id, master_subnet_id=self.master_subnet.id
        ).exclude(id=self.master_subnet.id)

        self.assertEqual(subnet_query.count(), rule.number_of_subnets)

    def test_sharable_vpn_vpnclient_subnet_multiple_rules(self):
        vpn_server = self._create_vpn(name='vpn-server', subnet=self.master_subnet)

        template = self._create_template(name='vpn-client', type='vpn', vpn=vpn_server)

        self.master_subnet.organization = None
        self.master_subnet.save()

        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org2')

        rule1 = self._get_vpn_subdivision_rule(organization=org1)
        rule2 = self._get_vpn_subdivision_rule(organization=org2)

        config1 = self._create_config(organization=org1)
        config2 = self._create_config(organization=org2)

        config1.templates.add(template)
        config2.templates.add(template)

        self.assertEqual(
            Subnet.objects.exclude(id=self.master_subnet.id).count(),
            rule1.number_of_subnets + rule2.number_of_subnets,
        )
        config1_subnets = config1.subnetdivisionindex_set.filter(
            ip__isnull=True, subnet__isnull=False
        ).values_list('subnet__subnet', flat=True)
        config2_subnets = config2.subnetdivisionindex_set.filter(
            ip__isnull=True, subnet__isnull=False
        ).values_list('subnet__subnet', flat=True)
        self.assertNotIn(config1_subnets.first(), config2_subnets)
        self.assertNotIn(config1_subnets.last(), config2_subnets)

    def test_device_deleted(self):
        rule = self._get_vpn_subdivision_rule()
        subnet_query = Subnet.objects.filter(organization_id=self.org.id).exclude(
            id=self.master_subnet.id
        )
        self.config.templates.add(self.template)
        self.assertEqual(
            subnet_query.count(), rule.number_of_subnets,
        )

        self.config.device.delete()
        self.assertEqual(
            subnet_query.count(), 0,
        )


class TestCeleryTasks(TestCase):
    def test_subnet_division_rule_does_not_exist(self):
        id = uuid.uuid4()
        log_message = (
            'Failed to {action} Subnet Division Rule with id: '
            f'"{id}", reason: SubnetDivisionRule matching query does not exist.'
        )
        with patch('logging.Logger.warning') as mocked_logger:
            tasks.update_subnet_division_index.run(id)
            mocked_logger.assert_called_once_with(
                log_message.format(action='update indexes for')
            )

        with patch('logging.Logger.warning') as mocked_logger:
            tasks.update_subnet_name_description.run(id)
            mocked_logger.assert_called_once_with(
                log_message.format(action='update subnets related to')
            )

        with patch('logging.Logger.warning') as mocked_logger:
            tasks.provision_extra_ips.run(id, old_number_of_ips=0)
            mocked_logger.assert_called_once_with(
                log_message.format(action='provision extra IPs for')
            )

import csv
from io import StringIO
from ipaddress import IPv4Network, IPv6Network, ip_network

from django.core.exceptions import ValidationError
from django.test import TestCase
from swapper import load_model

from openwisp_ipam.base.models import CsvImportException

from . import CreateModelsMixin

Subnet = load_model("openwisp_ipam", "Subnet")
IpAddress = load_model("openwisp_ipam", "IpAddress")


class TestModels(CreateModelsMixin, TestCase):
    def test_ip_address_string_representation(self):
        ipaddress = IpAddress(ip_address="entry ip_address")
        self.assertEqual(str(ipaddress), ipaddress.ip_address)

    def test_invalid_ipaddress_subnet(self):
        self._create_subnet(subnet="192.168.2.0/24")
        try:
            self._create_ipaddress(ip_address="10.0.0.2", subnet=Subnet.objects.first())
        except ValidationError as e:
            self.assertTrue(
                e.message_dict["ip_address"]
                == ["IP address does not belong to the subnet"]
            )
        else:
            self.fail("ValidationError not raised")

    def test_valid_ipaddress_subnet(self):
        self._create_subnet(subnet="192.168.2.0/24")
        try:
            self._create_ipaddress(
                ip_address="192.168.2.1", subnet=Subnet.objects.first()
            )
        except ValidationError:
            self.fail("ValidationError raised")

    def test_used_ipaddress(self):
        self._create_subnet(subnet="10.0.0.0/24")
        self._create_ipaddress(ip_address="10.0.0.1", subnet=Subnet.objects.first())
        try:
            self._create_ipaddress(ip_address="10.0.0.1", subnet=Subnet.objects.first())
        except ValidationError as e:
            self.assertTrue(
                e.message_dict["ip_address"] == ["IP address already used."]
            )
        else:
            self.fail("ValidationError not raised")

    def test_invalid_ipaddress(self):
        error_message = "'1234325' does not appear to be an IPv4 or IPv6 address"
        self._create_subnet(subnet="10.0.0.0/24")
        try:
            self._create_ipaddress(ip_address="1234325", subnet=Subnet.objects.first())
        except ValueError as e:
            self.assertEqual(str(e), error_message)
        else:
            self.fail("ValueError not raised")

    def test_available_ipv4(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24")
        self._create_ipaddress(ip_address="10.0.0.1", subnet=subnet)
        ipaddr = subnet.get_next_available_ip()
        self.assertEqual(str(ipaddr), "10.0.0.2")

    def test_available_ipv6(self):
        subnet = self._create_subnet(subnet="fdb6:21b:a477::9f7/64")
        self._create_ipaddress(ip_address="fdb6:21b:a477::1", subnet=subnet)
        ipaddr = subnet.get_next_available_ip()
        self.assertEqual(str(ipaddr), "fdb6:21b:a477::2")

    def test_unavailable_ip(self):
        subnet = self._create_subnet(subnet="10.0.0.0/32")
        # Consume the only available IP address in the subnet
        subnet.request_ip()
        # Try to request IP address from exhausted subnet
        ipaddr = subnet.get_next_available_ip()
        self.assertEqual(ipaddr, None)

    def test_request_ip_for_slash_32_subnet(self):
        # Regression test for provisioning IP from a /32 network
        subnet = self._create_subnet(subnet="10.0.0.1/32")
        ipaddr = subnet.get_next_available_ip()
        self.assertEqual(ipaddr, "10.0.0.1")

    def test_request_ipv4(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24")
        self._create_ipaddress(ip_address="10.0.0.1", subnet=subnet)
        ipaddr = subnet.request_ip()
        self.assertEqual(str(ipaddr), "10.0.0.2")

    def test_request_ipv6(self):
        subnet = self._create_subnet(subnet="fdb6:21b:a477::9f7/64")
        self._create_ipaddress(ip_address="fdb6:21b:a477::1", subnet=subnet)
        ipaddr = subnet.request_ip()
        self.assertEqual(str(ipaddr), "fdb6:21b:a477::2")

    def test_unavailable_request_ip(self):
        subnet = self._create_subnet(subnet="10.0.0.0/32")
        # Consume the only available IP address in the subnet
        subnet.request_ip()
        # Try to request IP address from exhausted subnet
        ipaddr = subnet.request_ip()
        self.assertEqual(ipaddr, None)

    def test_subnet_string_representation_with_name(self):
        subnet = Subnet(subnet="entry subnet", name="test1")
        self.assertEqual(str(subnet), "{0} {1}".format(subnet.name, str(subnet.subnet)))

    def test_valid_cidr_field(self):
        try:
            self._create_subnet(subnet="22.0.0.0/24")
        except ValidationError:
            self.fail("ValidationError raised")

    def test_invalid_cidr_field(self):
        error_message = [
            "'192.192.192.192.192' does not appear to be an IPv4 or IPv6 network"
        ]
        try:
            self._create_subnet(subnet="192.192.192.192.192")
        except ValidationError as e:
            self.assertTrue(e.message_dict["subnet"] == error_message)
        else:
            self.fail("ValidationError not raised")

    def test_overlapping_subnet(self):
        with self.subTest("10.0.0.0/24 overlaps with 10.0.0.0/16"):
            subnet1 = self._create_subnet(subnet="10.0.0.0/16")
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(
                    subnet="10.0.0.0/24", organization=subnet1.organization
                )
            message_dict = context_manager.exception.message_dict
            self.assertIn("subnet", message_dict)
            self.assertIn("Subnet overlaps with 10.0.0.0/16.", message_dict["subnet"])
            subnet1.delete()

        with self.subTest("10.0.0.0/16 overlaps with 10.0.0.0/24"):
            subnet1 = self._create_subnet(subnet="10.0.0.0/24")
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(
                    subnet="10.0.0.0/16", organization=subnet1.organization
                )
            message_dict = context_manager.exception.message_dict
            self.assertIn("subnet", message_dict)
            self.assertIn("Subnet overlaps with 10.0.0.0/24.", message_dict["subnet"])
            subnet1.delete()

        with self.subTest("different orgs do not overlap"):
            self._create_subnet(subnet="10.0.0.0/16")
            org2 = self._create_org(name="org2", slug="org2")
            self._create_subnet(subnet="10.0.0.0/24", organization=org2)

        with self.subTest("shared orgs overlaps with non shared"):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(subnet="10.0.0.0/8", organization=None)
            message_dict = context_manager.exception.message_dict
            self.assertIn("subnet", message_dict)
            self.assertIn(
                "Subnet overlaps with a subnet of another organization.",
                message_dict["subnet"],
            )

        with self.subTest("non shared subnet overlaps with shared"):
            Subnet.objects.all().delete()
            self._create_subnet(subnet="10.0.0.0/8", organization=None)
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(subnet="10.0.0.0/16")
            message_dict = context_manager.exception.message_dict
            self.assertIn("subnet", message_dict)
            self.assertIn("Subnet overlaps with 10.0.0.0/8.", message_dict["subnet"])

    def test_master_subnet_validation(self):
        master = self._create_subnet(subnet="10.0.0.0/23")
        org2 = self._create_org(name="org2", slug="org2")
        error_message = (
            "Please ensure that the organization of this subnet and "
            "the organization of the related subnet match."
        )
        with self.subTest("invalid master subnet"):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(subnet="192.168.2.0/24", master_subnet=master)
            message_dict = context_manager.exception.message_dict
            self.assertIn("master_subnet", message_dict)
            self.assertIn("Invalid master subnet.", message_dict["master_subnet"])

        with self.subTest("org1 master, org1 child: ok"):
            self._create_subnet(
                master_subnet=master,
                subnet="10.0.0.0/24",
                organization=master.organization,
            )

            self._create_subnet(
                master_subnet=master,
                subnet="10.0.1.0/24",
                organization=master.organization,
            )
            Subnet.objects.filter(master_subnet__isnull=False).delete()

        with self.subTest("org1 master, org2 child: reject"):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(
                    master_subnet=master, subnet="10.0.0.0/24", organization=org2
                )
            message_dict = context_manager.exception.message_dict
            self.assertIn("master_subnet", message_dict)
            self.assertIn(error_message, message_dict["master_subnet"])

        with self.subTest("org1 master, shared child: reject"):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(
                    master_subnet=master, subnet="10.0.0.0/24", organization=None
                )
            message_dict = context_manager.exception.message_dict
            self.assertIn(error_message, message_dict["master_subnet"])

        with self.subTest("shared master, org1 children: ok"):
            org1 = master.organization
            master.organization = None
            master.full_clean()
            master.save()
            org1_subnet = self._create_subnet(
                master_subnet=master,
                subnet="10.0.0.0/24",
                organization=org1,
            )
            org1_subnet.delete()

        with self.subTest(
            "shared master, org1 children, org2 overlapping children: reject"
        ):
            overlap_error_message = (
                "Subnet overlaps with a subnet of another organization."
            )
            duplicate_error_message = (
                "This subnet is already assigned to another organization."
            )
            org1 = self._get_org()
            org2 = self._create_org(name="test")
            master.organization = None
            master.full_clean()
            master.save()
            org1_subnet = self._create_subnet(
                master_subnet=master,
                subnet="10.0.0.0/24",
                organization=org1,
            )
            # Tests for overlapping subnets
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(
                    master_subnet=master, subnet="10.0.0.0/25", organization=org2
                )
            message_dict = context_manager.exception.message_dict
            self.assertIn(overlap_error_message, message_dict["subnet"])
            # Tests for duplicate subnet
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(
                    master_subnet=master, subnet="10.0.0.0/24", organization=org2
                )
            message_dict = context_manager.exception.message_dict
            self.assertIn(duplicate_error_message, message_dict["subnet"])

            org1_subnet.delete()

    def test_valid_subnet_relation_tree(self):
        subnet1 = self._create_subnet(subnet="12.0.56.0/24")
        try:
            subnet2 = self._create_subnet(subnet="12.0.56.0/25", master_subnet=subnet1)
            self._create_subnet(subnet="12.0.56.0/26", master_subnet=subnet2)
        except ValidationError:
            self.fail("Correct master_subnet not accepted")

    def test_invalid_subnet_relation_tree(self):
        subnet1 = self._create_subnet(subnet="12.0.56.0/24")
        self._create_subnet(subnet="12.0.56.0/25", master_subnet=subnet1)
        try:
            self._create_subnet(subnet="12.0.56.0/26", master_subnet=subnet1)
        except ValidationError as e:
            self.assertEqual(
                e.message_dict["subnet"], ["Subnet overlaps with 12.0.56.0/25."]
            )
        else:
            self.fail("ValidationError not raised")

    def test_save_none_subnet_fails(self):
        try:
            self._create_subnet(subnet=None)
        except ValidationError as err:
            self.assertTrue(
                err.message_dict["subnet"] == ["This field cannot be null."]
            )
        else:
            self.fail("ValidationError not raised")

    def test_save_blank_subnet_fails(self):
        try:
            self._create_subnet(subnet="")
        except ValidationError as err:
            self.assertTrue(
                err.message_dict["subnet"] == ["This field cannot be blank."]
            )
        else:
            self.fail("ValidationError not raised")

    def test_save_none_subnet_name_fails(self):
        try:
            self._create_subnet(name=None)
        except ValidationError as err:
            self.assertTrue(err.message_dict["name"] == ["This field cannot be null."])
        else:
            self.fail("ValidationError not raised")

    def test_save_blank_subnet_name_fails(self):
        try:
            self._create_subnet(name="")
        except ValidationError as err:
            self.assertTrue(err.message_dict["name"] == ["This field cannot be blank."])
        else:
            self.fail("ValidationError not raised")

    def test_retrieves_ipv4_ipnetwork_type(self):
        instance = self._create_subnet(subnet="10.1.2.0/24")
        instance = Subnet.objects.get(pk=instance.pk)
        self.assertIsInstance(instance.subnet, IPv4Network)

    def test_retrieves_ipv6_ipnetwork_type(self):
        instance = self._create_subnet(subnet="2001:db8::0/32")
        instance = Subnet.objects.get(pk=instance.pk)
        self.assertIsInstance(instance.subnet, IPv6Network)

    def test_incompatible_ipadresses(self):
        org = self._create_org(name="org", slug="org")
        master = self._create_subnet(
            name="IPv6", organization=org, subnet="2001:db8:85a3::64/128"
        )
        subnet_ip = "192.166.45.0/24"
        with self.assertRaises(ValidationError) as context_manager:
            self._create_subnet(
                name="IPv4",
                organization=org,
                subnet=subnet_ip,
                master_subnet=master,
            )
        message_dict = context_manager.exception.message_dict
        master_version = ip_network(master.subnet).version
        subnet_version = ip_network(subnet_ip).version
        error_message = (
            f"IP version mismatch: Subnet {subnet_ip} is IPv{subnet_version}, "
            f"but Master Subnet {master.subnet} is IPv{master_version}."
        )
        self.assertIn("master_subnet", message_dict)
        self.assertIn(error_message, message_dict["master_subnet"])

    def test_ipadresses_missing_attribute(self):
        instance = self._create_subnet(subnet="10.1.2.0/24")
        instance2 = self._create_subnet(subnet="10.1.3.0/25")
        del instance.subnet.network_address
        try:
            instance2.subnet.subnet_of(instance.subnet)
        except AttributeError as err:
            self.assertIn(
                str(err), "'IPv4Network' object has no attribute 'network_address'"
            )
        else:
            self.fail("TypeError not raised")

    def test_unique_subnet_multitenancy(self):
        subnet1 = self._create_subnet(subnet="10.0.0.0/24")

        with self.subTest("validation idempotent"):
            subnet1.full_clean()

        with self.subTest("same org"):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(
                    subnet="10.0.0.0/24", organization=subnet1.organization
                )
            message_dict = context_manager.exception.message_dict
            self.assertIn(
                "Subnet with this Subnet and Organization already exists.",
                str(message_dict),
            )

        shared = self._create_subnet(subnet="10.0.1.0/24", organization=None)

        with self.subTest("validation on shared indempotent"):
            shared.full_clean()

        with self.subTest("duplicate subnet within shared org"):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(subnet=shared.subnet, organization=None)
            message_dict = context_manager.exception.message_dict
            self.assertIn(
                "This subnet is already assigned for internal usage in the system",
                str(message_dict),
            )

        with self.subTest("duplicate subnet between shared org and non shared"):
            self._create_subnet(subnet="10.0.2.0/24", organization=None)
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(
                    subnet="10.0.2.0/24", organization=subnet1.organization
                )
            message_dict = context_manager.exception.message_dict
            self.assertIn(
                "This subnet is already assigned for internal usage in the system",
                str(message_dict),
            )

        with self.subTest("duplicate subnet between non shared and shared org"):
            self._create_subnet(subnet="10.0.3.0/24", organization=subnet1.organization)
            with self.assertRaises(ValidationError) as context_manager:
                self._create_subnet(subnet="10.0.3.0/24", organization=None)
            message_dict = context_manager.exception.message_dict
            self.assertIn(
                "This subnet is already assigned to another organization",
                str(message_dict),
            )

        with self.subTest("different org should be accepted"):
            org2 = self._create_org(name="org2", slug="org2")
            subnet2 = self._create_subnet(subnet="10.0.0.0/24", organization=org2)
            self.assertEqual(subnet2.organization, org2)

    def test_nested_overlapping_subnets(self):
        # Tests overlapping validation for nested subnets
        shared_level_0_subnet = self._create_subnet(
            subnet="10.0.0.0/16", organization=None
        )
        shared_level_1_subnet = self._create_subnet(
            subnet="10.0.1.0/24", master_subnet=shared_level_0_subnet, organization=None
        )
        org1_level_2_subnet = self._create_subnet(
            subnet="10.0.1.0/28", master_subnet=shared_level_1_subnet
        )
        self._create_subnet(subnet="10.0.1.0/31", master_subnet=org1_level_2_subnet)

    def test_validation_nested_child_subnets(self):
        # Tests child subnets are excluded from overlapping validation
        master_subnet = self._create_subnet(subnet="10.0.0.0/16")

        # Level 1 nesting
        a_level_1 = self._create_subnet(
            subnet="10.0.1.0/24", master_subnet=master_subnet
        )
        b_level_1 = self._create_subnet(
            subnet="10.0.2.0/24", master_subnet=master_subnet
        )

        # Level 2 nesting
        a_level_2 = self._create_subnet(subnet="10.0.1.8/29", master_subnet=a_level_1)
        self._create_subnet(subnet="10.0.1.16/29", master_subnet=a_level_1)
        b_level_2 = self._create_subnet(subnet="10.0.2.8/29", master_subnet=b_level_1)
        self._create_subnet(subnet="10.0.2.16/29", master_subnet=b_level_1)

        # Level 3 nesting
        self._create_subnet(subnet="10.0.1.8/31", master_subnet=a_level_2)
        self._create_subnet(subnet="10.0.2.8/31", master_subnet=b_level_2)

        master_subnet.full_clean()
        master_subnet.save()

    def test_read_row(self):
        data = "\n"
        reader = csv.reader(data, delimiter=",")
        self.assertEqual(Subnet()._read_row(reader), None)
        data = """subnet_name,
        subnet_value,
        org_slug,
        """
        buffer = StringIO()
        buffer.write(data)
        buffer.seek(0)
        reader = csv.reader(buffer, delimiter=",")
        self.assertEqual(Subnet()._read_row(reader), "subnet_name")
        self.assertEqual(Subnet()._read_row(reader), "subnet_value")
        self.assertEqual(Subnet()._read_row(reader), "org_slug")

    def test_get_or_create_org(self):
        _get_org = Subnet()._get_org
        self.assertEqual(_get_org(None), None)
        self.assertEqual(_get_org(""), None)
        with self.assertRaises(CsvImportException) as context_manager:
            _get_org("invalid slug")
        self.assertEqual(
            str(context_manager.exception),
            "['Enter a valid “slug” consisting of letters,"
            " numbers, underscores or hyphens.']",
        )
        with self.assertRaises(CsvImportException) as context_manager:
            _get_org("new-org")
        self.assertIn(
            "“new-org”",
            str(context_manager.exception),
        )

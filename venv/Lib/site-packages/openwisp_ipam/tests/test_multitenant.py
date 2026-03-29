from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openwisp_users.tests.utils import TestMultitenantAdminMixin
from swapper import load_model

from openwisp_ipam.api.utils import AuthorizeCSVImport

from . import CreateModelsMixin, PostDataMixin

User = get_user_model()
IpAddress = load_model("openwisp_ipam", "IPAddress")
Subnet = load_model("openwisp_ipam", "Subnet")
OrganizationUser = load_model("openwisp_users", "OrganizationUser")


class TestMultitenantAdmin(TestMultitenantAdminMixin, CreateModelsMixin, TestCase):
    app_label = "openwisp_ipam"

    def _create_multitenancy_test_env(self):
        org1 = self._create_org(name="test1organization")
        org2 = self._create_org(name="test2organization")
        subnet1 = self._create_subnet(subnet="172.16.0.1/16", organization=org1)
        subnet2 = self._create_subnet(subnet="192.168.0.1/16", organization=org2)
        ipadd1 = self._create_ipaddress(ip_address="172.16.0.1", subnet=subnet1)
        ipadd2 = self._create_ipaddress(ip_address="192.168.0.1", subnet=subnet2)
        operator = self._create_operator(organizations=[org1])
        data = dict(
            org1=org1,
            org2=org2,
            subnet1=subnet1,
            subnet2=subnet2,
            ipadd1=ipadd1,
            ipadd2=ipadd2,
            operator=operator,
        )
        return data

    def test_multitenancy_ip_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_ipaddress_changelist"),
            visible=[data["ipadd1"]],
            hidden=[data["ipadd2"]],
        )

    def test_multitenancy_subnet_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_subnet_changelist"),
            visible=[data["subnet1"].subnet],
            hidden=[data["subnet2"].subnet],
        )

    def test_import_subnet_permission(self):
        data = self._create_multitenancy_test_env()
        operator = data.get("operator")
        permission = Permission.objects.get(codename="add_subnet")
        operator.user_permissions.add(permission)
        self.client.login(username="operator", password="tester")

        with self.subTest("Import successful"):
            csv_data = """Monachers - Matera,
            10.27.1.0/24,
            test1organization,
            ip address,description
            10.27.1.1,Monachers"""
            csvfile = SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))
            self.assertEqual(Subnet.objects.count(), 2)
            response = self.client.post(
                reverse("admin:ipam_import_subnet"),
                {"csvfile": csvfile},
                follow=True,
            )
            self.assertContains(response, '<li class="success">Successfully imported')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(Subnet.objects.count(), 3)
            self.assertEqual(
                Subnet.objects.filter(subnet="10.27.1.0/24").exists(), True
            )

        with self.subTest("Import unsuccessful"):
            csv_data = """Monachers - Matera,
            10.27.1.0/24,
            test2organization,
            ip address,description
            10.27.1.1,Monachers"""
            csvfile = SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))
            response = self.client.post(
                reverse("admin:ipam_import_subnet"),
                {"csvfile": csvfile},
                follow=True,
            )
            self.assertContains(response, '<li class="error">You do not have')
            self.assertEqual(Subnet.objects.count(), 3)


class TestMultitenantApi(
    TestMultitenantAdminMixin, CreateModelsMixin, PostDataMixin, TestCase
):
    def setUp(self):
        super().setUp()
        # Creates a manager for each of org_a and org_b
        org_a = self._create_org(name="org_a", slug="org_a")
        org_b = self._create_org(name="org_b", slug="org_b")
        user_a = self._create_operator(
            username="user_a",
            email="usera@tester.com",
            password="tester",
            is_staff=True,
        )
        ou = OrganizationUser.objects.create(user=user_a, organization=org_a)
        ou.is_admin = True
        ou.save()
        user_b = self._create_operator(
            username="user_b",
            email="userb@tester.com",
            password="tester",
            is_staff=True,
        )
        ou = OrganizationUser.objects.create(user=user_b, organization=org_b)
        ou.is_admin = True
        ou.save()
        self._create_administrator(organizations=[org_a])
        # Creates a superuser
        self._create_operator(
            username="superuser",
            email="superuser@tester.com",
            password="tester",
            is_superuser=True,
        )

    def test_subnet(self):
        org_a = self._get_org(org_name="org_a")
        subnet = self._create_subnet(subnet="10.0.0.0/24", organization=org_a)
        url = reverse("ipam:subnet", args=(subnet.id,))

        with self.subTest("Test subnet accessible by org manager"):
            self._login(username="user_a", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["id"], str(subnet.id))

        with self.subTest("Test subnet accessible by superuser"):
            self._login(username="superuser", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["id"], str(subnet.id))

        with self.subTest("Test subnet NOT accessible by members of other orgs"):
            self._login(username="user_b", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_subnet_hosts(self):
        org_a = self._get_org(org_name="org_a")
        subnet = self._create_subnet(subnet="10.0.0.0/24", organization=org_a)
        url = reverse("ipam:hosts", args=(subnet.id,))

        with self.subTest("Test hosts list for org manager"):
            self._login(username="user_a", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test hosts list for superuser"):
            self._login(username="superuser", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test hosts list for non org manager"):
            self._login(username="user_b", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

    def test_subnet_list_ipaddress(self):
        org_a = self._get_org(org_name="org_a")
        subnet = self._create_subnet(subnet="10.0.0.0/24", organization=org_a)
        post_data = self._post_data(ip_address="10.0.0.5", subnet=str(subnet.id))
        url = reverse("ipam:list_create_ip_address", args=(subnet.id,))

        with self.subTest("Test ipaddress list for org manager"):
            self._login(username="superuser", password="tester")
            self.client.post(
                url,
                data=post_data,
                content_type="application/json",
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test ipaddress list for superuser"):
            self._login(username="user_a", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["results"][0]["ip_address"], "10.0.0.5")

        with self.subTest("Test ipaddress list not accessible by non org manager"):
            self._login(username="user_b", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

    def test_ipaddress(self):
        org_a = self._get_org(org_name="org_a")
        subnet = self._create_subnet(subnet="10.0.0.0/24", organization=org_a)
        ip_address = self._create_ipaddress(ip_address="10.0.0.5", subnet=subnet)
        url = reverse("ipam:ip_address", args=(ip_address.id,))

        with self.subTest("Test ipaddress accessible by superuser"):
            self._login(username="superuser", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["ip_address"], "10.0.0.5")

        with self.subTest("Test ipaddress accessible by org manager"):
            self._login(username="user_a", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["ip_address"], "10.0.0.5")

        with self.subTest("Test ipaddress NOT accessible by non org manager"):
            self._login(username="user_b", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_next_available_ip(self):
        org_a = self._get_org(org_name="org_a")
        subnet = self._create_subnet(subnet="10.0.0.0/24", organization=org_a)
        self._create_ipaddress(ip_address="10.0.0.1", subnet=subnet)
        url = reverse("ipam:get_next_available_ip", args=(subnet.id,))

        with self.subTest("Test next ip accessible by org manager"):
            self._login(username="user_a", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test next ip accessible by superuser"):
            self._login(username="superuser", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test next ip NOT accessible by org manager"):
            self._login(username="user_b", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

    def test_subnet_list(self):
        org_a = self._get_org(org_name="org_a")
        org_b = self._get_org(org_name="org_b")
        subnet1 = self._create_subnet(subnet="10.0.0.0/24", organization=org_a)
        subnet2 = self._create_subnet(subnet="10.10.0.0/24", organization=org_b)
        url = reverse("ipam:subnet_list_create")

        with self.subTest("Test subnet list filtered accorfingly for org_a manager"):
            self._login(username="user_a", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)
            self.assertEqual(response.data["results"][0]["id"], str(subnet1.id))

        with self.subTest("Test subnet list filtered accorfingly for tester"):
            self._login(username="superuser", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 2)

        with self.subTest("Test subnet list filtered accorfingly for org_b manager"):
            self._login(username="user_b", password="tester")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)
            self.assertEqual(response.data["results"][0]["id"], str(subnet2.id))

    def test_request_ip(self):
        org_a = self._get_org(org_name="org_a")
        subnet = self._create_subnet(subnet="10.0.0.0/24", organization=org_a)
        self._create_ipaddress(ip_address="10.0.0.1", subnet=subnet)
        post_data = {
            "path": reverse("ipam:request_ip", args=(subnet.id,)),
            "data": self._post_data(subnet=str(subnet.id), description="Testing"),
            "content_type": "application/json",
        }

        with self.subTest("Test request ip for org manager"):
            self._login(username="user_a", password="tester")
            response = self.client.post(**post_data)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data["ip_address"], "10.0.0.2")

        with self.subTest("Test request ip for superuser"):
            self._login(username="superuser", password="tester")
            response = self.client.post(**post_data)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data["ip_address"], "10.0.0.3")

        with self.subTest("Test request ip rejected for non org manager"):
            self._login(username="user_b", password="tester")
            response = self.client.post(**post_data)
            self.assertEqual(response.status_code, 404)

    def test_import_subnet(self):
        csv_data = """Monachers - Matera,
        10.27.1.0/24,
        org_a,
        ip address,description
        10.27.1.1,Monachers
        10.27.1.254,Nano Beam 5 19AC"""
        url = reverse("ipam:import-subnet")

        with self.subTest("Test import subnet successful for org manager"):
            self._login(username="administrator", password="tester")
            response = self.client.post(
                url,
                {"csvfile": SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))},
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test import subnet successful for superuser"):
            self._login(username="superuser", password="tester")
            response = self.client.post(
                url,
                {"csvfile": SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))},
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test import subnet unsuccessful for non org manager"):
            self._login(username="user_b", password="tester")
            response = self.client.post(
                url,
                {"csvfile": SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))},
            )
            self.assertEqual(response.status_code, 403)

    def test_import_subnet_new_org(self):
        csv_data = """Monachers - Matera,
        10.27.1.0/24,
        ,
        ip address,description
        10.27.1.1,Monachers
        10.27.1.254,Nano Beam 5 19AC"""
        with self.subTest("Test import subnet successful for org manager"):
            self._login(username="administrator", password="tester")
            response = self.client.post(
                reverse("ipam:import-subnet"),
                {"csvfile": SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))},
            )
            self.assertEqual(response.status_code, 200)

    def test_import_subnet_org_do_not_exist(self):
        csv_data = """Monachers - Matera,
        10.27.1.0/24,
        monachers,
        ip address,description
        10.27.1.1,Monachers
        10.27.1.254,Nano Beam 5 19AC"""
        self._login(username="administrator", password="tester")
        response = self.client.post(
            reverse("ipam:import-subnet"),
            {"csvfile": SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("The import operation failed", str(response.data.get("detail")))

    def test_invalid_csv_data(self):
        csv_data = """Monachers - Matera,
        10.27.1.0/24,"""
        self._login(username="administrator", password="tester")
        response = self.client.post(
            reverse("ipam:import-subnet"),
            {"csvfile": SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data.get("detail")), "Invalid data format")

    def test_export_subnet_api(self):
        org_a = self._get_org(org_name="org_a")
        subnet = self._create_subnet(
            subnet="10.0.0.0/24", name="Sample Subnet", organization=org_a
        )
        self._create_ipaddress(
            ip_address="10.0.0.1", subnet=subnet, description="Testing"
        )
        self._create_ipaddress(
            ip_address="10.0.0.2", subnet=subnet, description="Testing"
        )
        csv_data = """Sample Subnet\r
        10.0.0.0/24\r
        org_a\r
        \r
        ip_address,description\r
        10.0.0.1,Testing\r
        10.0.0.2,Testing\r
        """
        csv_data = bytes(csv_data.replace("        ", ""), "utf-8")
        url = reverse("ipam:export-subnet", args=(subnet.id,))

        with self.subTest("Test export subnet successful for org manager"):
            self._login(username="administrator", password="tester")
            response = self.client.post(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, csv_data)

        with self.subTest("Test export subnet successful for superuser"):
            self._login(username="superuser", password="tester")
            response = self.client.post(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, csv_data)

        with self.subTest("Test export subnet unsuccessful for non org manager"):
            self._login(username="user_b", password="tester")
            response = self.client.post(url)
            self.assertEqual(response.status_code, 404)

    def test_browsable_api_subnet_list(self):
        # Ensures the correct filtering of `SubnetSerializer`
        org_a = self._get_org(org_name="org_a")
        org_b = self._get_org(org_name="org_b")
        self._create_subnet(subnet="10.0.0.0/24", organization=org_a)
        self._create_subnet(subnet="10.10.0.0/24", organization=org_b)
        url = f'{reverse("ipam:subnet_list_create")}?format=api'

        with self.subTest(
            "Test `Organization` and `Master subnet` field filter for org manager"
        ):
            self._login(username="user_a", password="tester")
            response = self.client.get(url)
            self.assertContains(response, "org_a</option>")
            self.assertContains(response, "10.0.0.0/24</option>")
            self.assertNotContains(response, "org_b</option>")
            self.assertNotContains(response, "10.10.0.0/24</option>")

        with self.subTest(
            "Test `Organization` and `Master subnet` field filter for superuser"
        ):
            self._login(username="superuser", password="tester")
            response = self.client.get(url)
            self.assertContains(response, "org_a</option>")
            self.assertContains(response, "10.0.0.0/24</option>")
            self.assertContains(response, "org_b</option>")
            self.assertContains(response, "10.10.0.0/24</option>")

    def test_browsable_api_ipaddress_list(self):
        # Ensures the correct filtering of `IpAddressSerializer`
        org_a = self._get_org(org_name="org_a")
        org_b = self._get_org(org_name="org_b")
        subnet_a = self._create_subnet(subnet="10.0.0.0/24", organization=org_a)
        self._create_subnet(subnet="10.10.0.0/24", organization=org_b)
        url = (
            f'{reverse("ipam:list_create_ip_address", args=(subnet_a.id,))}'
            "?format=api"
        )

        with self.subTest("Test `Subnet` dropdown filter for org manager"):
            self._login(username="user_a", password="tester")
            response = self.client.get(url)
            self.assertContains(response, "10.0.0.0/24</option>")
            self.assertNotContains(response, "10.10.0.0/24</option>")

        with self.subTest("Test `Subnet` dropdown filter for superuser"):
            self._login(username="superuser", password="tester")
            response = self.client.get(url)
            self.assertContains(response, "10.0.0.0/24</option>")
            self.assertContains(response, "10.10.0.0/24</option>")

    def test_authorize_csv_import_implementation_error(self):
        with self.assertRaises(NotImplementedError):
            AuthorizeCSVImport.get_csv_organization(self)

        with self.assertRaises(NotImplementedError):
            AuthorizeCSVImport.get_user_organizations(self)

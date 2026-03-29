import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from . import CreateModelsMixin, PostDataMixin

User = get_user_model()
Subnet = load_model("openwisp_ipam", "Subnet")
IpAddress = load_model("openwisp_ipam", "IpAddress")


class TestAdmin(CreateModelsMixin, PostDataMixin, TestCase):
    app_label = "openwisp_ipam"

    def setUp(self):
        User.objects.create_superuser(
            username="admin", password="tester", email="admin@admin.com"
        )
        self.client.login(username="admin", password="tester")

    def test_non_existing_subnet_change_view(self):
        id = "00000000-0000-0000-0000-0000000000000"
        response = self.client.post(
            reverse(f"admin:{self.app_label}_subnet_change", args=[id]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"Subnet with ID “{id}” doesn’t exist. Perhaps it was deleted?",
            html=True,
        )

    def test_ipaddress_invalid_entry(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24", description="Sample Subnet")
        post_data = self._post_data(
            ip_address="1234",
            subnet=str(subnet.id),
            created_0="2017-08-08",
            created_1="15:16:10",
            modified_0="2017-08-08",
            modified_1="15:16:10",
        )
        response = self.client.post(
            reverse("admin:{0}_ipaddress_add".format(self.app_label)),
            json.loads(post_data),
            follow=True,
        )
        self.assertContains(response, "ok")
        self.assertContains(response, "Enter a valid IPv4 or IPv6 address.")

    def test_ipaddress_change(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24", description="Sample Subnet")
        obj = self._create_ipaddress(ip_address="10.0.0.1", subnet=subnet)

        response = self.client.get(
            reverse("admin:{0}_ipaddress_change".format(self.app_label), args=[obj.pk]),
            follow=True,
        )
        self.assertContains(response, "ok")
        self.assertEqual(IpAddress.objects.get(pk=obj.pk).ip_address, "10.0.0.1")

    def test_ipv4_subnet_change(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24", description="Sample Subnet")
        self._create_ipaddress(ip_address="10.0.0.1", subnet=subnet)
        url = reverse(
            "admin:{0}_subnet_change".format(self.app_label), args=[subnet.pk]
        )
        response = self.client.get(url)
        self.assertContains(response, "ok")
        self.assertContains(
            response, '<h3 class="subnet-visual">Subnet Visual Display</h3>'
        )

    def test_ipv6_subnet_change(self):
        subnet = self._create_subnet(
            subnet="fdb6:21b:a477::9f7/64", description="Sample Subnet"
        )
        self._create_ipaddress(ip_address="fdb6:21b:a477::9f7", subnet=subnet)

        response = self.client.get(
            reverse("admin:{0}_subnet_change".format(self.app_label), args=[subnet.pk]),
            follow=True,
        )
        self.assertContains(response, "ok")
        self.assertContains(
            response, '<h3 class="subnet-visual">Subnet Visual Display</h3>'
        )

    def test_subnet_invalid_entry(self):
        post_data = self._post_data(
            subnet=1234,
            created_0="2017-08-08",
            created_1="15:16:10",
            modified_0="2017-08-08",
            modified_1="15:16:10",
        )

        response = self.client.post(
            reverse("admin:{0}_subnet_add".format(self.app_label)),
            json.loads(post_data),
            follow=True,
        )
        self.assertContains(response, "ok")
        self.assertContains(response, "Enter a valid CIDR address.")

    def test_subnet_popup_response(self):
        subnet = self._create_subnet(
            subnet="fdb6:21b:a477::9f7/64", description="Sample Subnet"
        )
        self._create_ipaddress(ip_address="fdb6:21b:a477::9f7", subnet=subnet)
        change_path = reverse(
            "admin:{0}_subnet_change".format(self.app_label), args=[subnet.id]
        )
        response = self.client.get(
            f"{change_path}?_popup=1",
            follow=True,
        )
        self.assertContains(response, "ok")

    def test_add_ipaddress_response(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24", description="Sample Subnet")
        post_data = self._post_data(
            ip_address="10.0.0.1",
            subnet=str(subnet.id),
            created_0="2017-08-08",
            created_1="15:16:10",
            modified_0="2017-08-08",
            modified_1="15:16:10",
        )
        response = self.client.post(
            reverse("admin:{0}_ipaddress_add".format(self.app_label)),
            json.loads(post_data),
            follow=True,
        )
        self.assertContains(response, "ok")

    def test_change_ipaddress_response(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24", description="Sample Subnet")
        obj = self._create_ipaddress(ip_address="10.0.0.2", subnet=subnet)
        post_data = self._post_data(
            ip_address="10.0.0.2",
            subnet=str(subnet.id),
            created_0="2017-08-08",
            created_1="15:16:10",
            modified_0="2019-08-08",
            modified_1="15:16:10",
        )
        response = self.client.post(
            reverse(f"admin:{self.app_label}_ipaddress_change", args=[obj.pk]),
            json.loads(post_data),
            follow=True,
        )
        self.assertContains(response, "ok")

    def test_add_ipaddress_popup_response(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24", description="Sample Subnet")
        post_data = self._post_data(
            ip_address="10.0.0.1",
            subnet=str(subnet.id),
            created_0="2017-08-08",
            created_1="15:16:10",
            modified_0="2017-08-08",
            modified_1="15:16:10",
            _popup=1,
        )
        response = self.client.post(
            reverse("admin:{0}_ipaddress_add".format(self.app_label)),
            json.loads(post_data),
        )
        self.assertContains(
            response, "opener.dismissAddAnotherPopup(window, '10.0.0.1');"
        )

    def test_change_ipaddress_popup_response(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24", description="Sample Subnet")
        obj = self._create_ipaddress(ip_address="10.0.0.2", subnet=subnet)
        post_data = self._post_data(
            ip_address="10.0.0.2",
            subnet=str(subnet.id),
            created_0="2017-08-08",
            created_1="15:16:10",
            modified_0="2019-08-08",
            modified_1="15:16:10",
            _popup=1,
        )
        response = self.client.post(
            reverse(f"admin:{self.app_label}_ipaddress_change", args=[obj.pk]),
            json.loads(post_data),
        )
        self.assertContains(response, "opener.dismissAddAnotherPopup(window);")

    def test_csv_upload(self):
        self._create_org(name="Monachers", slug="monachers")
        csv_data = """Monachers - Matera,
        10.27.1.0/24,
        monachers,
        ,
        ip address,description
        10.27.1.1,Monachers
        10.27.1.252,NanoStation M5
        10.27.1.253,NanoStation M5
        10.27.1.254,Nano Beam 5 19AC"""
        csvfile = SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))
        response = self.client.post(
            reverse("admin:ipam_import_subnet"),
            {"csvfile": csvfile},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(Subnet.objects.first().subnet), "10.27.1.0/24")
        self.assertEqual(str(IpAddress.objects.all()[0].ip_address), "10.27.1.1")
        self.assertEqual(str(IpAddress.objects.all()[1].ip_address), "10.27.1.252")
        self.assertEqual(str(IpAddress.objects.all()[2].ip_address), "10.27.1.253")
        self.assertEqual(str(IpAddress.objects.all()[3].ip_address), "10.27.1.254")

    def test_existing_csv_data(self):
        subnet = self._create_subnet(name="Monachers - Matera", subnet="10.27.1.0/24")
        self._create_ipaddress(
            ip_address="10.27.1.1", subnet=subnet, description="Monachers"
        )
        csv_data = """Monachers - Matera,
        10.27.1.0/24,
        test-org,
        ip address,description
        10.27.1.1,Monachers
        10.27.1.252,NanoStation M5
        10.27.1.253,NanoStation M5
        10.27.1.254,Nano Beam 5 19AC"""
        csvfile = SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))
        response = self.client.post(
            reverse("admin:ipam_import_subnet"),
            {"csvfile": csvfile},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(IpAddress.objects.all()[1].ip_address), "10.27.1.252")
        self.assertEqual(str(IpAddress.objects.all()[2].ip_address), "10.27.1.253")
        self.assertEqual(str(IpAddress.objects.all()[3].ip_address), "10.27.1.254")

    def test_invalid_file_type(self):
        csv_data = """Monachers - Matera,
        10.27.1.0/24,
        ,
        ip address,description
        10.27.1.1,Monachers
        10.27.1.252,NanoStation M5
        10.27.1.253,NanoStation M5
        10.27.1.254,Nano Beam 5 19AC"""
        csvfile = SimpleUploadedFile("data.txt", bytes(csv_data, "utf-8"))
        response = self.client.post(
            reverse("admin:ipam_import_subnet"),
            {"csvfile": csvfile},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "File type not supported.")

    def test_invalid_subnet_csv_data(self):
        csv_data = """Monachers - Matera,
        12324324,
        ,
        ip address,description
        10.27.1.1,Monachers
        NanoStation M5
        10.27.1.253,NanoStation M5
        10.27.1.254,Nano Beam 5 19AC"""
        csvfile = SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))
        response = self.client.post(
            reverse("admin:ipam_import_subnet"),
            {"csvfile": csvfile},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not appear to be an IPv4 or IPv6 network")

    def test_invalid_ipaddress_csv_data(self):
        self._create_org(name="Monachers", slug="monachers")
        csv_data = """Monachers - Matera,
        10.27.1.0/24,
        monachers,
        ,
        ip address,description
        10123142131,Monachers
        10.27.1.252,NanoStation M5
        10.27.1.253,NanoStation M5
        10.27.1.254,Nano Beam 5 19AC"""
        csvfile = SimpleUploadedFile("data.csv", bytes(csv_data, "utf-8"))
        response = self.client.post(
            reverse("admin:ipam_import_subnet"),
            {"csvfile": csvfile},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not appear to be an IPv4 or IPv6 address")

    def test_subnet_csv_export(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24", name="Sample Subnet")
        self._create_ipaddress(
            ip_address="10.0.0.1", subnet=subnet, description="Testing"
        )
        self._create_ipaddress(
            ip_address="10.0.0.2", subnet=subnet, description="Testing"
        )
        self._create_ipaddress(ip_address="10.0.0.3", subnet=subnet)
        self._create_ipaddress(ip_address="10.0.0.4", subnet=subnet)

        csv_data = """Sample Subnet\r
        10.0.0.0/24\r
        test-org\r
        \r
        ip_address,description\r
        10.0.0.1,Testing\r
        10.0.0.2,Testing\r
        10.0.0.3,\r
        10.0.0.4,\r
        """
        csv_data = bytes(csv_data.replace("        ", ""), "utf-8")
        url = reverse("admin:ipam_export_subnet", args=[subnet.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, csv_data)

    def test_importcsv_form(self):
        response = self.client.get(reverse("admin:ipam_import_subnet"))
        self.assertEqual(response.status_code, 200)

    def test_hierarchy_tree(self):
        subnet_root = self._create_subnet(subnet="11.0.0.0/23", name="Root")
        subnet_child = self._create_subnet(
            subnet="11.0.0.0/24", name="Child#1", master_subnet=subnet_root
        )
        self._create_subnet(
            subnet="11.0.1.0/24", name="Child#2", master_subnet=subnet_root
        )
        self._create_subnet(
            subnet="11.0.0.0/25", name="Grantchild#1", master_subnet=subnet_child
        )
        url = reverse(
            "admin:{0}_subnet_change".format(self.app_label), args=[subnet_child.id]
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "11.0.0.0/23 (Root)")
        self.assertContains(response, "11.0.0.0/24 (Child#1)")
        self.assertContains(response, "11.0.1.0/24 (Child#2)")
        self.assertContains(response, "11.0.0.0/25 (Grantchild#1)")

    def test_subnet_add_rendered(self):
        url = reverse(f"admin:{self.app_label}_subnet_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_ipaddress_add_rendered(self):
        url = reverse(f"admin:{self.app_label}_ipaddress_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_change_view_master_multitenant(self):
        master1 = self._create_subnet(subnet="10.0.0.0/16")
        child1 = self._create_subnet(subnet="10.0.0.0/24", master_subnet=master1)
        org2 = self._create_org(name="org2", slug="org2")
        self._create_subnet(subnet="10.0.0.0/16", organization=org2)
        url = reverse(f"admin:{self.app_label}_subnet_change", args=[child1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_group_permission(self):
        admin = Group.objects.get(name="Administrator")
        admin_permissions = [
            "add_ipaddress",
            "change_ipaddress",
            "delete_ipaddress",
            "view_ipaddress",
            "add_subnet",
            "change_subnet",
            "delete_subnet",
            "view_subnet",
        ]
        perms = list(admin.permissions.values_list("codename", flat=True))
        for p in admin_permissions:
            self.assertIn(p, perms)

    def test_operator_group_permission(self):
        operator = Group.objects.get(name="Operator")
        operator_permissions = [
            "add_ipaddress",
            "change_ipaddress",
            "delete_ipaddress",
            "view_ipaddress",
            "view_subnet",
        ]
        perms = list(operator.permissions.values_list("codename", flat=True))
        for p in operator_permissions:
            self.assertIn(p, perms)

    def test_admin_menu_items(self):
        # Test menu items (openwisp-utils menu) for Subnet and IpAddress models
        models = [
            "ipaddress",
            "subnet",
        ]
        response = self.client.get(reverse("admin:index"))
        for model in models:
            with self.subTest(f"test_admin_group_for_{model}_model"):
                url = reverse(f"admin:{self.app_label}_{model}_changelist")
                self.assertContains(response, f'class="mg-link" href="{url}"')
        with self.subTest("test_ipam_group_is_registered"):
            self.assertContains(
                response,
                '<div class="mg-dropdown-label">Ipam </div>',
                html=True,
            )

    def test_operator_import_export_subnet(self):
        def assert_response(response):
            self.assertEqual(response.redirect_chain[0], (reverse("admin:index"), 302))
            self.assertEqual(response.status_code, 200)

        operator = User.objects.create_user(
            username="operator",
            password="tester",
            is_staff=True,
            email="tester@openwisp.org",
        )
        Group.objects.filter(name="Operator").first().user_set.add(operator)
        self.client.login(username="operator", password="tester")
        with self.subTest("test_operator_subnet_import"):
            response = self.client.get(reverse("admin:ipam_import_subnet"), follow=True)
            assert_response(response)
        subnet = self._create_subnet(subnet="10.0.0.0/24", name="Test Subnet")
        with self.subTest("test_operator_subnet_export"):
            response = self.client.get(
                reverse("admin:ipam_export_subnet", args=[subnet.id]), follow=True
            )
            assert_response(response)

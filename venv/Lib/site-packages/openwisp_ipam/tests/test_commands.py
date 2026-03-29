import glob
import os
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase
from swapper import load_model

from . import CreateModelsMixin, FileMixin

Subnet = load_model("openwisp_ipam", "Subnet")
IpAddress = load_model("openwisp_ipam", "IpAddress")


class TestCommands(CreateModelsMixin, FileMixin, TestCase):
    def test_export_subnet_command(self):
        subnet = self._create_subnet(subnet="10.0.0.0/24", name="Sample Subnet")
        self._create_ipaddress(
            ip_address="10.0.0.1", subnet=subnet, description="Testing"
        )
        self._create_ipaddress(
            ip_address="10.0.0.2", subnet=subnet, description="Testing"
        )
        self._create_ipaddress(ip_address="10.0.0.3", subnet=subnet)
        self._create_ipaddress(ip_address="10.0.0.4", subnet=subnet)
        out = StringIO()
        call_command("export_subnet", "10.0.0.0/24", stdout=out)
        self.assertIn("Successfully exported 10.0.0.0/24", out.getvalue())
        with self.assertRaises(CommandError):
            call_command("export_subnet", "11.0.0.0./24")
        with self.assertRaises(CommandError):
            call_command("export_subnet", "11.0.0.0/24")

    def test_import_subnet_command(self):
        self._create_org(name="Ham Ninux", slug="ham-ninux")
        with self.assertRaises(CommandError):
            call_command(
                "import_subnet", file=self._get_path("static/invalid_data.csv")
            )
        self.assertEqual(Subnet.objects.all().count(), 0)
        self.assertEqual(IpAddress.objects.all().count(), 0)
        call_command("import_subnet", file=self._get_path("static/import_data.xlsx"))
        self.assertEqual(Subnet.objects.all().count(), 1)
        self.assertEqual(IpAddress.objects.all().count(), 8)
        with self.assertRaises(CommandError):
            call_command("import_subnet", file="invalid.pdf")
        with self.assertRaises(CommandError):
            call_command("import_subnet", file="invalid_path.csv")

    @classmethod
    def tearDownClass(cls):
        files = glob.glob("data_[a-z0-9]*.csv")
        for file in files:
            os.remove(file)

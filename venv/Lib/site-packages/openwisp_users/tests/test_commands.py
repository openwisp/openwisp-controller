import csv
from io import StringIO
from unittest.mock import patch

from django.core.files.temp import NamedTemporaryFile
from django.core.management import call_command
from django.test import TestCase
from rest_framework.authtoken.models import Token

from openwisp_utils.tests import capture_stdout

from .. import settings as app_settings
from .utils import TestOrganizationMixin


class TestManagementCommands(TestOrganizationMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.temp_file = NamedTemporaryFile(mode="wt", delete=False)

    def tearDown(self):
        super().tearDown()
        self.temp_file.close()

    def test_export_users(self):
        org1 = self._create_org(name="org1")
        org2 = self._create_org(name="org2")
        user = self._create_user()
        operator = self._create_operator()
        admin = self._create_admin()
        self._create_org_user(organization=org1, user=user, is_admin=True)
        self._create_org_user(organization=org2, user=user, is_admin=False)
        self._create_org_user(organization=org2, user=operator, is_admin=False)
        stdout = StringIO()
        with self.assertNumQueries(2):
            call_command("export_users", filename=self.temp_file.name, stdout=stdout)
        self.assertIn(
            f"User data exported successfully to {self.temp_file.name}",
            stdout.getvalue(),
        )

        # Read the content of the temporary file
        with open(self.temp_file.name, "r") as temp_file:
            csv_reader = csv.reader(temp_file)
            csv_data = list(csv_reader)

        # 3 user and 1 header
        self.assertEqual(len(csv_data), 4)
        self.assertEqual(
            csv_data[0], app_settings.EXPORT_USERS_COMMAND_CONFIG["fields"]
        )
        # Ensuring ordering
        self.assertEqual(csv_data[1][0], str(user.id))
        self.assertEqual(csv_data[2][0], str(operator.id))
        self.assertEqual(csv_data[3][0], str(admin.id))
        # Check organizations formatting
        self.assertEqual(csv_data[1][-1], f"({org1.id},True)\n({org2.id},False)")
        self.assertEqual(csv_data[2][-1], f"({org2.id},False)")
        self.assertEqual(csv_data[3][-1], "")

    @capture_stdout()
    def test_exclude_fields(self):
        self._create_user()
        call_command(
            "export_users",
            filename=self.temp_file.name,
            exclude_fields=",".join(
                app_settings.EXPORT_USERS_COMMAND_CONFIG["fields"][1:]
            ),
        )
        with open(self.temp_file.name, "r") as temp_file:
            csv_reader = csv.reader(temp_file)
            csv_data = list(csv_reader)

        # 1 user and 1 header
        self.assertEqual(len(csv_data), 2)
        self.assertEqual(csv_data[0], ["id"])

    @patch.object(
        app_settings,
        "EXPORT_USERS_COMMAND_CONFIG",
        {"fields": ["id", "auth_token.key"]},
    )
    def test_related_fields(self):
        user = self._create_user()
        token = Token.objects.create(user=user)
        stdout = StringIO()
        with self.assertNumQueries(2):
            call_command("export_users", filename=self.temp_file.name, stdout=stdout)
        self.assertIn(
            f"User data exported successfully to {self.temp_file.name}",
            stdout.getvalue(),
        )

        # Read the content of the temporary file
        with open(self.temp_file.name, "r") as temp_file:
            csv_reader = csv.reader(temp_file)
            csv_data = list(csv_reader)

        # 3 user and 1 header
        self.assertEqual(len(csv_data), 2)
        self.assertEqual(
            csv_data[0], app_settings.EXPORT_USERS_COMMAND_CONFIG["fields"]
        )
        self.assertEqual(csv_data[1][0], str(user.id))
        self.assertEqual(csv_data[1][1], str(token.key))

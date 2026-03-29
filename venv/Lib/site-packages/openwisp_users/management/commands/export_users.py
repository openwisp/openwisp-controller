import csv

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand

from ... import settings as app_settings

User = get_user_model()


class Command(BaseCommand):
    help = "Exports user data to a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--exclude-fields",
            dest="exclude_fields",
            default="",
            help="Comma-separated list of fields to exclude from export",
        )
        parser.add_argument(
            "--filename",
            dest="filename",
            default="openwisp_exported_users.csv",
            help=(
                "Filename for the exported CSV, defaults to"
                ' "openwisp_exported_users.csv"'
            ),
        )

    def handle(self, *args, **options):
        fields = app_settings.EXPORT_USERS_COMMAND_CONFIG.get("fields", []).copy()
        # Get the fields to be excluded from the command-line argument
        exclude_fields = options.get("exclude_fields").split(",")
        # Remove excluded fields from the export fields
        fields = [field for field in fields if field not in exclude_fields]
        # Fetch all user data in a single query using select_related for related models
        queryset = User.objects.select_related(
            *app_settings.EXPORT_USERS_COMMAND_CONFIG.get("select_related", []),
        ).order_by("date_joined")

        # Prepare a CSV writer
        filename = options.get("filename")
        csv_file = open(filename, "w", newline="")
        csv_writer = csv.writer(csv_file)

        # Write header row
        csv_writer.writerow(fields)

        # Write data rows
        for user in queryset.iterator():
            data_row = []
            for field in fields:
                # Extract the value from related models
                if "." in field:
                    related_model, related_field = field.split(".")
                    try:
                        related_value = getattr(
                            getattr(user, related_model), related_field
                        )
                    except ObjectDoesNotExist:
                        data_row.append("")
                    else:
                        data_row.append(related_value)
                elif field == "organizations":
                    organizations = []
                    for org_id, user_perm in user.organizations_dict.items():
                        organizations.append(f'({org_id},{user_perm["is_admin"]})')
                    data_row.append("\n".join(organizations))
                else:
                    data_row.append(getattr(user, field))
            csv_writer.writerow(data_row)

        # Close the CSV file
        csv_file.close()
        self.stdout.write(
            self.style.SUCCESS(f"User data exported successfully to {filename}!")
        )

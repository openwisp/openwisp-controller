from django.db import migrations

from . import assign_permissions_to_groups


class Migration(migrations.Migration):
    dependencies = [
        ("pki", "0011_disallowed_blank_key_length_or_digest"),
    ]
    operations = [
        migrations.RunPython(
            assign_permissions_to_groups, reverse_code=migrations.RunPython.noop
        )
    ]

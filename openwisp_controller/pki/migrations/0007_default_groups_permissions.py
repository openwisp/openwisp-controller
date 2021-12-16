from django.db import migrations

from . import assign_permissions_to_groups


class Migration(migrations.Migration):
    dependencies = [
        ('pki', '0006_add_x509_passphrase_field'),
    ]
    operations = [
        migrations.RunPython(
            assign_permissions_to_groups, reverse_code=migrations.RunPython.noop
        )
    ]

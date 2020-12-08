from django.db import migrations

from . import assign_permissions_to_groups


class Migration(migrations.Migration):
    dependencies = [('connection', '0002_credentials_auto_add')]

    operations = [
        migrations.RunPython(
            assign_permissions_to_groups, reverse_code=migrations.RunPython.noop
        )
    ]

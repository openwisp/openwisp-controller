from django.db import migrations

from . import allow_operator_view_organization


class Migration(migrations.Migration):
    dependencies = [("openwisp_users", "0017_user_language")]

    operations = [
        migrations.RunPython(
            allow_operator_view_organization, reverse_code=migrations.RunPython.noop
        )
    ]

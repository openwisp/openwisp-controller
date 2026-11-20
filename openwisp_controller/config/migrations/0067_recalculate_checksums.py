"""Repair checksums changed by the netjsonconfig UTF-8 archive fix."""

from django.db import migrations
from swapper import dependency, load_model


def recalculate_checksums(apps, schema_editor):
    Config = load_model("config", "Config")
    for config in Config.objects.using(schema_editor.connection.alias).iterator():
        config.update_status_if_checksum_changed()


class Migration(migrations.Migration):
    dependencies = [
        ("config", "0066_whoisinfo_cidr_index"),
        dependency("config", "Config"),
    ]

    operations = [
        migrations.RunPython(recalculate_checksums, migrations.RunPython.noop),
    ]

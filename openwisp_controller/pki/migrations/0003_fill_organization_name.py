# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def forward(apps, schema_editor):
    """
    Fills the organization_name field of the following models:
        * ``openwisp_controller.pki.Ca``
        * ``openwisp_controller.pki.Cert``
    """
    if not schema_editor.connection.alias == 'default':
        return
    from ..models import Ca, Cert

    for model in [Ca, Cert]:
        for obj in model.objects.all():
            obj.organization_name = obj.x509.get_subject().organizationName or ''
            obj.save()


class Migration(migrations.Migration):
    dependencies = [
        ('pki', '0002_add_organization_name'),
    ]

    operations = [
        migrations.RunPython(forward, reverse_code=migrations.RunPython.noop),
    ]

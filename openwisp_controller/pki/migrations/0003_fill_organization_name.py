# -*- coding: utf-8 -*-
from django.db import migrations

from ..models import Ca, Cert


def forward(apps, schema_editor):
    """
    Fills the organization_name field of the following models:
        * ``openwisp_controller.pki.Ca``
        * ``openwisp_controller.pki.Cert``
    """
    if not schema_editor.connection.alias == 'default':
        return
    ca_model = apps.get_model('pki', 'Ca')
    cert_model = apps.get_model('pki', 'Cert')

    for model, real_model in [(ca_model, Ca), (cert_model, Cert)]:
        for obj in model.objects.all():
            model_instance = real_model.objects.get(pk=obj.pk)
            obj.organization_name = (
                model_instance.x509.get_subject().organizationName or ''
            )
            obj.save()


class Migration(migrations.Migration):
    dependencies = [('pki', '0002_add_organization_name')]

    operations = [migrations.RunPython(forward, reverse_code=migrations.RunPython.noop)]

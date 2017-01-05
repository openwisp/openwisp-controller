from django.contrib import admin

from django_x509.base.admin import CaAdmin as BaseCaAdmin
from django_x509.base.admin import CertAdmin as BaseCertAdmin

from .models import Ca, Cert


class CaAdmin(BaseCaAdmin):
    fields = ['name',
              'organization',
              'notes',
              'key_length',
              'digest',
              'validity_start',
              'validity_end',
              'country_code',
              'state',
              'city',
              'email',
              'common_name',
              'extensions',
              'serial_number',
              'certificate',
              'private_key',
              'created',
              'modified']


CaAdmin.list_display.insert(1, 'organization')


class CertAdmin(BaseCertAdmin):
    fields = ['name',
              'organization',
              'ca',
              'notes',
              'revoked',
              'revoked_at',
              'key_length',
              'digest',
              'validity_start',
              'validity_end',
              'country_code',
              'state',
              'city',
              'email',
              'common_name',
              'extensions',
              'serial_number',
              'certificate',
              'private_key',
              'created',
              'modified']


admin.site.register(Ca, CaAdmin)
admin.site.register(Cert, CertAdmin)

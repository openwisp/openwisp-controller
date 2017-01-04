from django.contrib import admin

from django_x509.base.admin import CaAdmin as BaseCaAdmin

from .models import Ca


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


admin.site.register(Ca, CaAdmin)

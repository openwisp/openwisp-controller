from django.contrib import admin
from django_x509.base.admin import CaAdmin as BaseCaAdmin
from django_x509.base.admin import CertAdmin as BaseCertAdmin
from reversion.admin import VersionAdmin

from openwisp_utils.admin import MultitenantOrgFilter

from ..admin import MultitenantAdminMixin
from .models import Ca, Cert


class CaAdmin(MultitenantAdminMixin, VersionAdmin, BaseCaAdmin):
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
              'organization_name',
              'email',
              'common_name',
              'extensions',
              'serial_number',
              'certificate',
              'private_key',
              'created',
              'modified']


CaAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))
CaAdmin.list_display.insert(1, 'organization')


class CertAdmin(MultitenantAdminMixin, VersionAdmin, BaseCertAdmin):
    multitenant_shared_relations = ('ca',)
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
              'organization_name',
              'email',
              'common_name',
              'extensions',
              'serial_number',
              'certificate',
              'private_key',
              'created',
              'modified']


CertAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))
CertAdmin.list_filter.remove('ca')
CertAdmin.list_display.insert(1, 'organization')


admin.site.register(Ca, CaAdmin)
admin.site.register(Cert, CertAdmin)

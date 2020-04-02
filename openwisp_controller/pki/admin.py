from django.contrib import admin
from django_x509.base.admin import AbstractCaAdmin, AbstractCertAdmin
from reversion.admin import VersionAdmin

from openwisp_users.multitenancy import MultitenantOrgFilter

from ..admin import MultitenantAdminMixin
from .models import Ca, Cert


class CaAdmin(MultitenantAdminMixin, VersionAdmin, AbstractCaAdmin):
    history_latest_first = True


CaAdmin.fields.insert(2, 'organization')
CaAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))
CaAdmin.list_display.insert(1, 'organization')
CaAdmin.Media.js += ('admin/pki/js/show-org-field.js',)


class CertAdmin(MultitenantAdminMixin, VersionAdmin, AbstractCertAdmin):
    multitenant_shared_relations = ('ca',)
    history_latest_first = True


CertAdmin.fields.insert(2, 'organization')
CertAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))
CertAdmin.list_filter.remove('ca')
CertAdmin.list_display.insert(1, 'organization')
CertAdmin.Media.js += ('admin/pki/js/show-org-field.js',)


admin.site.register(Ca, CaAdmin)
admin.site.register(Cert, CertAdmin)

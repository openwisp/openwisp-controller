from django.contrib import admin
from django_x509.base.admin import AbstractCaAdmin, AbstractCertAdmin
from reversion.admin import VersionAdmin
from swapper import load_model

from openwisp_users.multitenancy import MultitenantOrgFilter

from ..admin import MultitenantAdminMixin

Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')


@admin.register(Ca)
class CaAdmin(MultitenantAdminMixin, AbstractCaAdmin, VersionAdmin):
    history_latest_first = True


CaAdmin.fields.insert(2, 'organization')
CaAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))
CaAdmin.list_display.insert(1, 'organization')
CaAdmin.Media.js += ('admin/pki/js/show-org-field.js',)


@admin.register(Cert)
class CertAdmin(MultitenantAdminMixin, AbstractCertAdmin, VersionAdmin):
    multitenant_shared_relations = ('ca',)
    history_latest_first = True


CertAdmin.fields.insert(2, 'organization')
CertAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))
CertAdmin.list_filter.remove('ca')
CertAdmin.list_display.insert(1, 'organization')
CertAdmin.Media.js += ('admin/pki/js/show-org-field.js',)

"""
base/admin.py and admin.py are not merged
to keep backward compatibility; otherwise,
there is no reason for the existence of the
base/admin.py file.
"""

from django.contrib import admin
from swapper import load_model

from .base.admin import AbstractCaAdmin, AbstractCertAdmin

Ca = load_model("django_x509", "Ca")
Cert = load_model("django_x509", "Cert")


class CertAdmin(AbstractCertAdmin):
    pass


class CaAdmin(AbstractCaAdmin):
    pass


admin.site.register(Ca, CaAdmin)
admin.site.register(Cert, CertAdmin)

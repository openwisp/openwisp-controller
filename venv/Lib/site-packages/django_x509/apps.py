from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DjangoX509Config(AppConfig):
    name = "django_x509"
    verbose_name = _("x509 Certificates")
    default_auto_field = "django.db.models.AutoField"

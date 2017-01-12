from django_x509.base.views import crl

from .models import Ca

crl.ca_model = Ca

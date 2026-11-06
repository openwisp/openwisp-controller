"""Registers the openwisp-ipam URLs with the subnet division API views.

``openwisp_ipam.urls.get_urls()`` accepts a module of custom API views and
falls back to its own for anything the module does not define. This allows
the subnet division app to report deletions refused by its rules at the
REST boundary, instead of letting the refusal surface as a server error.
"""

from openwisp_ipam.urls import get_urls

from .api import views as api_views

urlpatterns = get_urls(api_views)

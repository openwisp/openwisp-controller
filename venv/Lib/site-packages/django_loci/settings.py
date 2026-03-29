from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

DJANGO_LOCI_GEOCODER = getattr(settings, "DJANGO_LOCI_GEOCODER", "ArcGIS")
DJANGO_LOCI_GEOCODE_FAILURE_DELAY = getattr(
    settings, "DJANGO_LOCI_GEOCODE_FAILURE_DELAY", 1
)
DJANGO_LOCI_GEOCODE_RETRIES = getattr(settings, "DJANGO_LOCI_GEOCODE_RETRIES", 3)
DJANGO_LOCI_GEOCODE_API_KEY = getattr(
    settings, "DJANGO_LOCI_GEOCODE_GOOGLE_API_KEY", None
)
FLOORPLAN_STORAGE = getattr(
    settings, "LOCI_FLOORPLAN_STORAGE", "django_loci.storage.OverwriteStorage"
)

try:
    FLOORPLAN_STORAGE = import_string(FLOORPLAN_STORAGE)
except ImportError:  # pragma: nocover
    raise ImproperlyConfigured("Import of {0} failed".format(FLOORPLAN_STORAGE))

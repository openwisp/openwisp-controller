import logging

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Warning, register
from django.utils.translation import gettext_lazy as _

from .base.geocoding_views import geocode
from .channels.receivers import load_location_receivers

logger = logging.getLogger(__name__)


@register("geocoding", deploy=True)
def test_geocoding(app_configs=None, **kwargs):
    warnings = []
    # do not run check during development, testing or if feature is disabled
    if not settings.DEBUG or not getattr(settings, "TESTING", False):
        location = geocode("Red Square")
        if not location:
            warnings.append(
                Warning(
                    "Geocoding service is experiencing issues or is not properly configured"
                )
            )
    return warnings


class LociConfig(AppConfig):
    name = "django_loci"
    verbose_name = _("django-loci")
    default_auto_field = "django.db.models.AutoField"

    def __setmodels__(self):
        """
        this method can be overridden in 3rd party apps
        """
        from .models import Location

        self.location_model = Location

    def ready(self):
        import leaflet

        leaflet.app_settings["NO_GLOBALS"] = False
        self.__setmodels__()
        self._load_receivers()

    def _load_receivers(self):
        load_location_receivers(sender=self.location_model)

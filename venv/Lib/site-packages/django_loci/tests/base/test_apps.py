from unittest.mock import patch

from django.conf import settings
from django.core.checks import Warning

from ...apps import test_geocoding
from .. import TestLociMixin


class BaseTestApps(TestLociMixin):
    @patch("django_loci.apps.geocode", return_value=None)
    @patch.object(settings, "TESTING", False)
    def test_geocode_strict(self, geocode_mocked):
        warning = test_geocoding()
        self.assertEqual(
            warning,
            [
                Warning(
                    "Geocoding service is experiencing issues or is not properly configured"
                )
            ],
        )
        geocode_mocked.assert_called_once()

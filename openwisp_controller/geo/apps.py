import swapper
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django_loci.apps import LociConfig


class GeoConfig(LociConfig):
    name = 'openwisp_controller.geo'
    label = 'geo'
    verbose_name = _('Geographic Information')

    def __setmodels__(self):
        self.location_model = swapper.load_model('geo', 'Location')

    def ready(self):
        super().ready()
        if getattr(settings, 'TESTING', False):
            self._add_params_to_test_config()

    def _add_params_to_test_config(self):
        """
        this methods adds the management fields of DeviceLocationInline
        to the parameters used in config.tests.test_admin.TestAdmin
        this hack is needed for the following reasons:
            - avoids breaking config.tests.test_admin.TestAdmin
            - avoids adding logic of geo app in config, this
              way config doesn't know anything about geo, keeping
              complexity down to a sane level
        """
        from ..config.tests.test_admin import TestAdmin as TestConfigAdmin
        from .tests.test_admin_inline import TestAdminInline

        params = TestAdminInline._get_params()
        delete_keys = []
        # delete unnecessary fields
        # leave only management fields
        for key in params.keys():
            if '_FORMS' not in key:
                delete_keys.append(key)
        for key in delete_keys:
            del params[key]
        TestConfigAdmin._additional_params.update(params)

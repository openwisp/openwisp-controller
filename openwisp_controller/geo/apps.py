import swapper
from django.conf import settings
from django.db.models import Case, Count, Sum, When
from django.utils.translation import ugettext_lazy as _
from django_loci.apps import LociConfig

from openwisp_utils.admin_theme import register_dashboard_chart


class GeoConfig(LociConfig):
    name = 'openwisp_controller.geo'
    label = 'geo'
    verbose_name = _('Geographic Information')

    def __setmodels__(self):
        self.location_model = swapper.load_model('geo', 'Location')

    def ready(self):
        super().ready()
        self.register_dashboard_charts()
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

    def register_dashboard_charts(self):
        register_dashboard_chart(
            position=2,
            config={
                'name': _('Geographic positioning'),
                'query_params': {
                    'app_label': 'config',
                    'model': 'device',
                    'annotate': {
                        'with_geo': Count(
                            Case(When(devicelocation__isnull=False, then=1,))
                        ),
                        'without_geo': Count(
                            Case(When(devicelocation__isnull=True, then=1,))
                        ),
                    },
                    'aggregate': {
                        'with_geo__sum': Sum('with_geo'),
                        'without_geo__sum': Sum('without_geo'),
                    },
                },
                'colors': {'with_geo__sum': '#267126', 'without_geo__sum': '#353c44'},
                'labels': {
                    'with_geo__sum': _('With geographic position'),
                    'without_geo__sum': _('Without geographic position'),
                },
                'filters': {
                    'key': 'with_geo',
                    'with_geo__sum': 'true',
                    'without_geo__sum': 'false',
                },
            },
        )

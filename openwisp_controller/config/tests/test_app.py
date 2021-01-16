from django.test import TestCase

from openwisp_utils.admin_theme.dashboard import DASHBOARD_CONFIG


class TestCustomAdminDashboard(TestCase):
    def test_controller_element_registered(self):
        expected_config = {
            'name': 'Configuration Status',
            'query_params': {
                'app_label': 'config',
                'model': 'device',
                'group_by': 'config__status',
            },
            'colors': {'applied': 'green', 'modified': 'orange', 'error': 'red'},
        }
        element_config = DASHBOARD_CONFIG.get(1, None)
        self.assertNotEqual(element_config, None)
        self.assertDictEqual(element_config, expected_config)

from django.test import TestCase

from openwisp_utils.admin_theme.dashboard import DASHBOARD_CHARTS


class TestApps(TestCase):
    def test_config_status_chart_registered(self):
        expected_config = {
            'name': 'Configuration Status',
            'query_params': {
                'app_label': 'config',
                'model': 'device',
                'group_by': 'config__status',
            },
            'colors': {
                'applied': '#267126',
                'modified': '#ffb442',
                'error': '#a72d1d',
                'deactivating': '#353c44',
                'deactivated': '#000',
            },
            'labels': {
                'applied': 'applied',
                'error': 'error',
                'modified': 'modified',
                'deactivating': 'deactivating',
                'deactivated': 'deactivated',
            },
        }
        chart_config = DASHBOARD_CHARTS.get(1, None)
        self.assertIsNotNone(chart_config)
        self.assertDictEqual(chart_config, expected_config)

    def test_device_models_chart_registered(self):
        chart_config = DASHBOARD_CHARTS.get(10, None)
        self.assertIsNotNone(chart_config)
        self.assertEqual(chart_config['name'], 'Device Models')
        self.assertIn('labels', chart_config)
        self.assertDictEqual(chart_config['labels'], {'': 'undefined'})
        self.assertNotIn('filters', chart_config)
        query_params = chart_config['query_params']
        self.assertIn('group_by', query_params)
        self.assertEqual(query_params['group_by'], 'model')

    def test_firmware_version_chart_registered(self):
        chart_config = DASHBOARD_CHARTS.get(11, None)
        self.assertIsNotNone(chart_config)
        self.assertEqual(chart_config['name'], 'Firmware version')
        self.assertIn('labels', chart_config)
        self.assertDictEqual(chart_config['labels'], {'': 'undefined'})
        self.assertNotIn('filters', chart_config)
        query_params = chart_config['query_params']
        self.assertIn('group_by', query_params)
        self.assertEqual(query_params['group_by'], 'os')

    def test_system_type_chart_registered(self):
        chart_config = DASHBOARD_CHARTS.get(12, None)
        self.assertIsNotNone(chart_config)
        self.assertEqual(chart_config['name'], 'System type')
        self.assertIn('labels', chart_config)
        self.assertDictEqual(chart_config['labels'], {'': 'undefined'})
        self.assertNotIn('filters', chart_config)
        query_params = chart_config['query_params']
        self.assertIn('group_by', query_params)
        self.assertEqual(query_params['group_by'], 'system')

    def test_device_group_chart_registered(self):
        chart_config = DASHBOARD_CHARTS.get(20, None)
        self.assertIsNotNone(chart_config)
        self.assertEqual(chart_config['name'], 'Groups')
        self.assertIn('labels', chart_config)
        self.assertDictEqual(
            chart_config['labels'],
            {'active': 'Active groups', 'empty': 'Empty groups'},
        )
        self.assertIn('filters', chart_config)
        query_params = chart_config['query_params']
        self.assertNotIn('group_by', query_params)
        self.assertIn('annotate', query_params)
        self.assertIn('aggregate', query_params)
        self.assertIn('filters', chart_config)
        filters = chart_config['filters']
        self.assertIn('key', filters)
        self.assertIn('active', chart_config['filters'])
        self.assertIn('empty', chart_config['filters'])

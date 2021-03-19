from django.test import TestCase

from openwisp_utils.admin_theme.dashboard import DASHBOARD_CHARTS


class TestApps(TestCase):
    def test_geo_chart_registered(self):
        chart_config = DASHBOARD_CHARTS.get(2, None)
        self.assertIsNotNone(chart_config)
        self.assertEqual(chart_config['name'], 'Geographic positioning')
        self.assertIn('labels', chart_config)
        query_params = chart_config['query_params']
        self.assertIn('annotate', query_params)
        self.assertIn('aggregate', query_params)
        self.assertIn('filters', chart_config)
        filters = chart_config['filters']
        self.assertIn('key', filters)
        self.assertIn('with_geo__sum', chart_config['filters'])
        self.assertIn('without_geo__sum', chart_config['filters'])

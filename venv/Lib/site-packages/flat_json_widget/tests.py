from django.test import TestCase

from flat_json_widget.widgets import FlatJsonWidget


class TestFlatJsonWidget(TestCase):
    def test_render(self):
        widget = FlatJsonWidget()
        html = widget.render(name="content", value=None)
        self.assertIn("flat-json-original-textarea", html)
        self.assertIn("flat-json-textarea", html)
        self.assertIn("icon-addlink.svg", html)
        self.assertIn("icon-changelink.svg", html)

    def test_media(self):
        widget = FlatJsonWidget()
        html = widget.media.render()
        expected_list = [
            "/static/flat-json-widget/css/flat-json-widget.css",
            "/static/flat-json-widget/js/lib/underscore-umd-min.js",
            "/static/flat-json-widget/js/flat-json-widget.js",
        ]
        for expected in expected_list:
            self.assertIn(expected, html)

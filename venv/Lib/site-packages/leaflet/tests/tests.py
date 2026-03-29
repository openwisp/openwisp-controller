import django
from django.contrib.admin import ModelAdmin, StackedInline
from django.contrib.admin.options import BaseModelAdmin, InlineModelAdmin
from django.contrib.gis.db import models as gismodels
from django.contrib.staticfiles.storage import StaticFilesStorage
from django.test import SimpleTestCase

from .. import PLUGINS, PLUGIN_FORMS, _normalize_plugins_config

from ..templatetags import leaflet_tags
from ..admin import LeafletGeoAdmin, LeafletGeoAdminMixin
from ..forms.widgets import LeafletWidget
from ..forms import fields


class DummyStaticFilesStorage(StaticFilesStorage):

    def url(self, name):
        raise ValueError


class PluginListingTest(SimpleTestCase):

    def test_default_resources(self):
        PLUGINS.update({
            'a': {'css': 'a'},
            'b': {'css': 'b', 'auto-include': True},
            'c': {'css': 'c'},
        })
        PLUGINS.pop('__is_normalized__')
        _normalize_plugins_config()

        names = leaflet_tags._get_plugin_names(None)
        resources = leaflet_tags._get_all_resources_for_plugins(names, 'css')
        self.assertEqual(['/static/b'], resources)

    def test_all_resources(self):
        PLUGINS.update({
            'a': {'css': 'a'},
            'b': {'css': 'b'},
            'c': {'css': 'c'},
        })
        PLUGINS.pop('ALL')
        PLUGINS.pop(PLUGIN_FORMS)
        PLUGINS.pop('__is_normalized__')
        _normalize_plugins_config()

        names = leaflet_tags._get_plugin_names('ALL')
        resources = leaflet_tags._get_all_resources_for_plugins(names, 'css')
        self.assertEqual(['/static/a', '/static/b', '/static/c'],
                         sorted(resources))

    def test_explicit_resources(self):
        PLUGINS.update({
            'a': {'css': 'a'},
            'b': {'css': 'b'},
            'c': {'css': 'c'},
        })
        PLUGINS.pop('__is_normalized__')
        _normalize_plugins_config()

        names = leaflet_tags._get_plugin_names('a,c')
        resources = leaflet_tags._get_all_resources_for_plugins(names, 'css')
        self.assertEqual(['/static/a', '/static/c'], sorted(resources))


class TemplateTagTest(SimpleTestCase):

    def test_default_layer_in_leaflet_map(self):
        context = leaflet_tags.leaflet_map('map')
        self.assertEqual('map', context['name'])
        self.assertTrue('"OSM", "//tile.openstreetmap.org/{z}/{x}/{y}.png"' in
                        context['djoptions'])


class LeafletWidgetRenderingTest(SimpleTestCase):
    def test_default_media(self):
        widget = LeafletWidget()
        media = widget.media
        self.assertEqual([], media.render_js())
        self.assertEqual([], list(media.render_css()))

    def test_included_media(self):
        class LeafletWidgetMedia(LeafletWidget):
            include_media = True

        widget = LeafletWidgetMedia()
        media = widget.media
        media_js = "".join(media.render_js())
        media_css = "".join(media.render_css())
        self.assertIn('leaflet/leaflet.js', media_js)
        self.assertIn('leaflet/leaflet.extras.js', media_js)
        self.assertIn('leaflet/leaflet.forms.js', media_js)
        self.assertIn('leaflet/draw/leaflet.draw.js', media_js)

        self.assertIn('leaflet/leaflet.css', media_css)
        self.assertIn('leaflet/draw/leaflet.draw.css', media_css)

    def test_widget_geometry_is_empty_string(self):
        widget = LeafletWidget()
        widget.render('geom', '', {'id': 'geom'})
        self.assertTrue(True, 'We should\'t accept blank geometry in value.')

    def test_widget_get_attrs_deprecation(self):
        widget = LeafletWidget()
        with self.assertWarns(DeprecationWarning):
            priv_result = widget._get_attrs("foo")
        pub_result = widget.get_attrs("foo")
        self.assertEqual(
            priv_result, pub_result,
            msg=(
                'Deprecated \'LeafletWidget._get_attrs\' does not have the the same '
                'output as public method \'LeafletWidget.get_attrs\'.'
            )
        )


class LeafletFieldsWidgetsTest(SimpleTestCase):
    def test_default_widget(self):
        for typ in ['Geometry', 'Point', 'MultiPoint', 'LineString', 'Polygon',
                    'MultiLineString', 'MultiPolygon', 'GeometryCollection']:
            f = getattr(fields, typ + 'Field')()
            self.assertTrue(isinstance(f.widget, LeafletWidget))
            self.assertEqual(f.widget.geom_type, typ.upper())


class DummyAdminSite:
    """
    Mock adminsite, which is required by InlineModelAdmin.__init__
    """

    def is_registered(self, model):
        return True


class DummyModel(gismodels.Model):
    geom = gismodels.PointField()

    class Meta:
        app_label = "leaflet"


class DummyInlineModel(gismodels.Model):
    geom = gismodels.PointField()

    class Meta:
        app_label = "leaflet"


class BaseLeafletGeoAdminTest:
    modeladmin_class = None  # type: BaseModelAdmin
    leafletgeoadmin_class = None  # type: LeafletGeoAdmin

    def setUp(self):
        self.modeladmin = self.leafletgeoadmin_class(DummyModel, DummyAdminSite())
        self.geomfield = DummyModel._meta.get_field('geom')
        self.formfield = self.modeladmin.formfield_for_dbfield(self.geomfield, None)

    def test_widget_for_field(self):
        widget = self.formfield.widget
        self.assertTrue(issubclass(widget.__class__, LeafletWidget))

    def test_widget_parameters(self):
        widget = self.formfield.widget
        self.assertEqual(widget.geom_type, 'POINT')
        self.assertEqual(widget.settings_overrides, {'DEFAULT_CENTER': (8.0, 3.15), })
        self.assertTrue(widget.modifiable)

    def test_widget_media(self):
        widget = self.formfield.widget
        media = widget.media
        media_js = "".join(media.render_js())
        media_css = "".join(media.render_css())
        self.assertIn('leaflet/leaflet.js', media_js)
        self.assertIn('leaflet/leaflet.extras.js', media_js)
        self.assertIn('leaflet/leaflet.forms.js', media_js)
        self.assertIn('leaflet/draw/leaflet.draw.js', media_js)

        self.assertIn('leaflet/leaflet.css', media_css)
        self.assertIn('leaflet/draw/leaflet.draw.css', media_css)

    def test_is_subclass_of_modeladmin(self):
        self.assertTrue(issubclass(self.leafletgeoadmin_class, self.modeladmin_class))


class DummyAdminSettingsOverridesMixin:
    settings_overrides = {
        'DEFAULT_CENTER': (8.0, 3.15),
    }


class DummyMixinModelAdmin(DummyAdminSettingsOverridesMixin, LeafletGeoAdminMixin, ModelAdmin):
    pass


class LeafletGeoAdminMixinTest(BaseLeafletGeoAdminTest, SimpleTestCase):
    modeladmin_class = ModelAdmin
    leafletgeoadmin_class = DummyMixinModelAdmin

    def test_is_not_subclass_of_modeladmin(self):
        self.assertFalse(issubclass(LeafletGeoAdminMixin, BaseModelAdmin))


class DummyModelAdmin(DummyAdminSettingsOverridesMixin, LeafletGeoAdmin):
    pass


class LeafletGeoAdminTest(BaseLeafletGeoAdminTest, SimpleTestCase):
    modeladmin_class = ModelAdmin
    leafletgeoadmin_class = DummyModelAdmin


class DummyMixinStackedInline(DummyAdminSettingsOverridesMixin, LeafletGeoAdminMixin, StackedInline):
    model = DummyInlineModel


class LeafletGeoAdminStackedInlineTest(BaseLeafletGeoAdminTest, SimpleTestCase):
    modeladmin_class = InlineModelAdmin
    leafletgeoadmin_class = DummyMixinStackedInline


class LeafletWidgetMapTest(SimpleTestCase):

    def test_default_parameters(self):
        widget = LeafletWidget()
        output = widget.render('geom', '', {'id': 'geom'})
        self.assertIn(".fieldid = 'geom'", output)
        self.assertIn(".srid = 4326", output)
        self.assertIn(".geom_type = 'Geometry'", output)
        self.assertIn('name="geom" hidden', output)
        self.assertIn('function geom_map_callback(map, options)', output)

    def test_overriden_parameters(self):
        class PolygonWidget(LeafletWidget):
            geom_type = 'POLYGON'
        widget = PolygonWidget()
        output = widget.render('geometry', '', {'id': 'geometry'})
        self.assertIn(".fieldid = 'geometry'", output)
        self.assertIn(".geom_type = 'Polygon'", output)
        self.assertIn('name="geometry" hidden', output)
        self.assertIn('function geometry_map_callback(map, options)', output)

    def test_javascript_safe_callback_name(self):
        widget = LeafletWidget()
        output = widget.render('prefix-geom', '')
        self.assertIn('function prefix_geom_map_callback(map, options)', output)
        output = widget.render('geom', '', {'id': 'prefix-geom'})
        self.assertIn('function prefix_geom_map_callback(map, options)', output)


class SettingsOverridesTest(SimpleTestCase):

    def test_settings_overrides(self):
        widget = LeafletWidget(attrs={
            'settings_overrides': {
                'DEFAULT_CENTER': (8.0, 3.14),
            }
        })
        output = widget.render('geom', '', {'id': 'geom'})
        self.assertIn('"center": [8.0, 3.14]', output)

    def test_spatial_extent_settings_overrides(self):
        widget = LeafletWidget(attrs={
            'settings_overrides': {
                'SPATIAL_EXTENT': (
                    3.812255859375,
                    50.387507803003146,
                    4.0869140625,
                    50.523904629228625,
                ),
                'DEFAULT_ZOOM': None,
                'DEFAULT_CENTER': None,
            }
        })
        output = widget.render('geom', '', {'id': 'geom'})
        self.assertIn('"extent": [[50.387507803003146, 3.812255859375], [50.523904629228625, 4.0869140625]]', output)
        self.assertIn('"center": null', output)
        self.assertIn('"zoom": null', output)


class LeafletModelFormTest(SimpleTestCase):

    def test_modelform_field_conformity(self):
        class DummyForm(django.forms.ModelForm):
            geom = fields.PointField()

            class Meta:
                model = DummyModel
                fields = ['geom']

        form = DummyForm()
        output = form.as_p()
        self.assertIn(".geom_type = 'Point'", output)

    def test_modelform_widget_conformity(self):
        class DummyForm(django.forms.ModelForm):
            class Meta:
                model = DummyModel
                fields = ['geom']
                widgets = {'geom': LeafletWidget()}
        form = DummyForm()
        output = form.as_p()
        self.assertIn(".geom_type = 'Point'", output)


class LeafletGeoAdminMapTest(LeafletGeoAdminTest):

    def test_widget_template_overriden(self):
        widget = self.formfield.widget
        output = widget.render('geom', '', {'id': 'geom'})
        self.assertIn('<div id="geom-div-map">', output)
        self.assertEqual(
            list(widget.media.render_css()),
            [
                '<link href="/static/leaflet/leaflet.css" media="screen" rel="stylesheet">',
                '<link href="/static/leaflet/leaflet_django.css" media="screen" rel="stylesheet">',
                '<link href="/static/leaflet/draw/leaflet.draw.css" media="screen" rel="stylesheet">',
            ]
        )

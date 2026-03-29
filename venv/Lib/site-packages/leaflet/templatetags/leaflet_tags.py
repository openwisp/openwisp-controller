import json

from django import template
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.encoding import force_str
from django.utils.translation import gettext as _
from django.templatetags.static import static

from leaflet import (app_settings, SPATIAL_EXTENT, SRID, PLUGINS, PLUGINS_DEFAULT,
                     PLUGIN_ALL, PLUGIN_FORMS)


register = template.Library()


@register.inclusion_tag('leaflet/css.html')
def leaflet_css(plugins=None):
    """

    :param only_plugins:
    :param exclude_plugins:
    :return:
    """
    plugin_names = _get_plugin_names(plugins)
    return {
        "PLUGINS_CSS": _get_all_resources_for_plugins(plugin_names, 'css'),
    }


@register.inclusion_tag('leaflet/js.html')
def leaflet_js(plugins=None):
    """

    :param only_plugins:
    :param exclude_plugins:
    :return:
    """
    plugin_names = _get_plugin_names(plugins)
    with_forms = PLUGIN_FORMS in plugin_names or PLUGIN_ALL in plugin_names
    FORCE_IMAGE_PATH = app_settings.get('FORCE_IMAGE_PATH')
    template_options = settings.TEMPLATES[0].get('OPTIONS', None)

    if template_options and 'debug' in template_options:
        debug = template_options['debug']
    else:
        debug = False

    return {
        "DEBUG": debug,
        "SRID": str(SRID) if SRID else None,
        "PLUGINS_JS": _get_all_resources_for_plugins(plugin_names, 'js'),
        "with_forms": with_forms,
        "FORCE_IMAGE_PATH": FORCE_IMAGE_PATH,
        "reset_view_icon": static("leaflet/images/reset-view.png")
    }


@register.inclusion_tag('leaflet/_leaflet_map.html')
def leaflet_map(name, callback=None, fitextent=True, creatediv=True,
                loadevent=app_settings.get('LOADEVENT'),
                settings_overrides={}, csp_nonce=None):
    """

    :param name:
    :param callback:
    :param fitextent:
    :param creatediv:
    :param loadevent:
    :param settings_overrides:
    :return:
    """

    if settings_overrides == '':
        settings_overrides = {}

    instance_app_settings = app_settings.copy()  # Allow not overidding global app_settings
    instance_app_settings.update(**settings_overrides)

    extent = None
    if instance_app_settings['SPATIAL_EXTENT'] is not None:
        # Leaflet uses [lat, lng]
        xmin, ymin, xmax, ymax = instance_app_settings['SPATIAL_EXTENT']
        bbox = (ymin, xmin, ymax, xmax)
        extent = [bbox[:2], bbox[2:4]]

    djoptions = dict(
        srid=SRID,
        extent=extent,
        fitextent=fitextent,
        center=instance_app_settings['DEFAULT_CENTER'],
        zoom=instance_app_settings['DEFAULT_ZOOM'],
        precision=instance_app_settings['DEFAULT_PRECISION'],
        minzoom=instance_app_settings['MIN_ZOOM'],
        maxzoom=instance_app_settings['MAX_ZOOM'],
        layers=[(force_str(label), url, attrs) for (label, url, attrs) in instance_app_settings.get('TILES')],
        overlays=[(force_str(label), url, attrs) for (label, url, attrs) in instance_app_settings.get('OVERLAYS')],
        attributionprefix=force_str(instance_app_settings.get('ATTRIBUTION_PREFIX'), strings_only=True),
        scale=instance_app_settings.get('SCALE'),
        minimap=instance_app_settings.get('MINIMAP'),
        resetview=instance_app_settings.get('RESET_VIEW'),
        tilesextent=list(instance_app_settings.get('TILES_EXTENT', []))
    )

    return {
        # templatetag options
        'name': name,
        'loadevents': json.dumps(loadevent.split(), cls=DjangoJSONEncoder),
        'creatediv': creatediv,
        'callback': callback,
        # initialization options
        'djoptions': json.dumps(djoptions, cls=DjangoJSONEncoder),
        # settings
        'NO_GLOBALS': instance_app_settings.get('NO_GLOBALS'),
        'csp_nonce': csp_nonce
    }


@register.inclusion_tag('leaflet/leaflet_draw_i18n.html', takes_context=True)
def leaflet_draw_i18n(context):
    return {
        "Control_ResetView_TITLE": _("Reset view"),
        "with_forms": context.get("with_forms", False),
        "draw_toolbar_actions_title": _("Cancel drawing"),
        "draw_toolbar_actions_text": _("Cancel"),
        "draw_toolbar_undo_title": _("Delete last point drawn"),
        "draw_toolbar_undo_text": _("Delete last point"),
        "draw_toolbar_buttons_polyline": _("Draw a polyline"),
        "draw_toolbar_buttons_polygon": _("Draw a polygon"),
        "draw_toolbar_buttons_rectangle": _("Draw a rectangle"),
        "draw_toolbar_buttons_circle": _("Draw a circle"),
        "draw_toolbar_buttons_marker": _("Draw a marker"),
        "draw_handlers_circle_tooltip_start": _("Click and drag to draw circle."),
        "draw_handlers_marker_tooltip_start": _("Click map to place marker."),
        "draw_handlers_polygon_tooltip_start": _("Click to start drawing shape."),
        "draw_handlers_polygon_tooltip_cont": _("Click to continue drawing shape."),
        "draw_handlers_polygon_tooltip_end": _("Click first point to close this shape."),
        "draw_handlers_polyline_error": _("<strong>Error:</strong> shape edges cannot cross!"),
        "draw_handlers_polyline_tooltip_start": _("Click to start drawing line."),
        "draw_handlers_polyline_tooltip_cont": _("Click to continue drawing line."),
        "draw_handlers_polyline_tooltip_end": _("Click last point to finish line."),
        "draw_handlers_rectangle_tooltip_start": _("Click and drag to draw rectangle."),
        "draw_handlers_simpleshape_tooltip_end": _("Release mouse to finish drawing."),
        "edit_toolbar_actions_save_title": _("Save changes."),
        "edit_toolbar_actions_save_text": _("Save"),
        "edit_toolbar_actions_cancel_title": _("Cancel editing, discards all changes."),
        "edit_toolbar_actions_cancel_text": _("Cancel"),
        "edit_toolbar_buttons_edit": _("Edit layers"),
        "edit_toolbar_buttons_editDisabled": _("No layers to edit."),
        "edit_toolbar_buttons_remove": _("Delete layers"),
        "edit_toolbar_buttons_removeDisabled": _("No layers to delete."),
        "edit_handlers_edit_tooltip_text": _("Drag handles, or marker to edit feature."),
        "edit_handlers_edit_tooltip_subtext": _("Click cancel to undo changes."),
        "edit_handlers_remove_tooltip_text": _("Click on a feature to remove"),
    }


@register.simple_tag
def leaflet_json_config():
    settings_as_json = app_settings.copy()

    if SPATIAL_EXTENT is not None:
        xmin, ymin, xmax, ymax = settings_as_json.pop('SPATIAL_EXTENT')
        settings_as_json['SPATIAL_EXTENT'] = {'xmin': xmin, 'ymin': ymin,
                                              'xmax': xmax, 'ymax': ymax}

    return json.dumps(settings_as_json, cls=DjangoJSONEncoder)


def _get_plugin_names(plugin_names_from_tag_parameter):
    """
    Returns a list of plugin names, specified in the parameter.
    Used by tags to determine which plugins to include
    :param pluging_names_parameter:
    :return:
    """
    if isinstance(plugin_names_from_tag_parameter, str):
        names = plugin_names_from_tag_parameter.split(',')
        return [n.strip() for n in names]
    else:
        return [PLUGINS_DEFAULT]


def _get_all_resources_for_plugins(plugin_names, resource_type):
    """
    Returns a list of URLs for the plugins with the specified resource type (js, css, ...)
    :param plugin_names:
    :param resource_type:
    :return:
    """
    result = []
    for plugin_name in plugin_names:
        if plugin_name in PLUGINS:
            result.extend(PLUGINS[plugin_name].get(resource_type, []))

    return result

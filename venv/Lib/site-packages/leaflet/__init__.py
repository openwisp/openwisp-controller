from collections import OrderedDict
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _
from django.utils.functional import lazy, Promise

DEFAULT_TILES = [(_('OSM'), '//tile.openstreetmap.org/{z}/{x}/{y}.png',
                  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')]

LEAFLET_CONFIG = getattr(settings, 'LEAFLET_CONFIG', {})
app_settings = dict({
    'TILES': DEFAULT_TILES,
    'OVERLAYS': [],
    'ATTRIBUTION_PREFIX': None,
    'LOADEVENT': 'load',
    'DEFAULT_ZOOM': None,
    'MIN_ZOOM': None,
    'MAX_ZOOM': None,
    'DEFAULT_CENTER': None,
    'DEFAULT_PRECISION': 6,
    'FORCE_IMAGE_PATH': False,
    'SRID': None,
    'TILES_EXTENT': [],
    'SCALE': 'metric',
    'MINIMAP': False,
    'RESET_VIEW': True,
    'NO_GLOBALS': True,
    'PLUGINS': OrderedDict(),
    'SPATIAL_EXTENT': (-180, -90, 180, 90),
}, **LEAFLET_CONFIG)


# If TILES is a string, convert to tuple
if isinstance(app_settings.get('TILES'), str):
    app_settings['TILES'] = [(_('Background'), app_settings.get('TILES'), '')]


# Verify that scale setting is valid.  For backwards-compatibility, interpret 'True' as 'metric'.
SCALE = app_settings.get("SCALE", None)
if SCALE is True:
    app_settings["SCALE"] = 'metric'
elif SCALE not in ('metric', 'imperial', 'both', None, False):
    raise ImproperlyConfigured("LEAFLET_CONFIG['SCALE'] must be True, False, None, 'metric', 'imperial' or 'both'.")


SPATIAL_EXTENT = app_settings.get("SPATIAL_EXTENT")
if SPATIAL_EXTENT is not None and not isinstance(SPATIAL_EXTENT, (tuple, list)) or len(SPATIAL_EXTENT) != 4:
    raise ImproperlyConfigured(_("Spatial extent should be a tuple (minx, miny, maxx, maxy)"))


SRID = app_settings.get("SRID")
if SRID == 3857:  # Leaflet's default, do not setup custom projection machinery
    SRID = None


TILES_EXTENT = app_settings.get("TILES_EXTENT")
# Due to bug in Leaflet/Proj4Leaflet ()
# landscape extents are not supported.
if SRID and TILES_EXTENT and (TILES_EXTENT[2] - TILES_EXTENT[0] > TILES_EXTENT[3] - TILES_EXTENT[1]):
    raise ImproperlyConfigured('Landscape tiles extent not supported (%s).' % (TILES_EXTENT,))


DEFAULT_CENTER = app_settings['DEFAULT_CENTER']
if DEFAULT_CENTER is not None and not (isinstance(DEFAULT_CENTER, (list, tuple)) and len(DEFAULT_CENTER) == 2):
    raise ImproperlyConfigured("LEAFLET_CONFIG['DEFAULT_CENTER'] must be an list/tuple with two elements - (lat, lon)")


DEFAULT_ZOOM = app_settings['DEFAULT_ZOOM']
if DEFAULT_ZOOM is not None and not (isinstance(DEFAULT_ZOOM, int) and (1 <= DEFAULT_ZOOM <= 24)):
    raise ImproperlyConfigured("LEAFLET_CONFIG['DEFAULT_ZOOM'] must be an int between 1 and 24.")


DEFAULT_PRECISION = app_settings['DEFAULT_PRECISION']
if DEFAULT_PRECISION is not None and not (isinstance(DEFAULT_PRECISION, int) and (4 <= DEFAULT_PRECISION <= 12)):
    raise ImproperlyConfigured("LEAFLET_CONFIG['DEFAULT_PRECISION'] must be an int between 4 and 12.")


PLUGINS = app_settings['PLUGINS']
if not (isinstance(PLUGINS, dict) and all([isinstance(el, dict) for el in PLUGINS.values()])):
    error_msg = """LEAFLET_CONFIG['PLUGINS'] must be dict of dicts in the format:
    { '[plugin_name]': { 'js': '[path-to-js]', 'css': '[path-to-css]' } } .)"""
    raise ImproperlyConfigured(error_msg)

PLUGIN_ALL = 'ALL'
PLUGINS_DEFAULT = '__default__'
PLUGIN_FORMS = 'forms'

# Add plugins required for forms (not auto-included)
# Assets will be preprended to any existing entry in PLUGINS['forms']
_forms_js = ['leaflet/draw/leaflet.draw.js',
             'leaflet/leaflet.forms.js']
if SRID:
    _forms_js += ['leaflet/proj4.js',
                  'leaflet/proj4leaflet.js',
                  'proj4js/%s.js' % SRID]

_forms_css = ['leaflet/draw/leaflet.draw.css']
_forms_plugins = PLUGINS.setdefault(PLUGIN_FORMS, {})
_forms_plugins['js'] = _forms_js + _forms_plugins.get('js', [])
_forms_plugins['css'] = _forms_css + _forms_plugins.get('css', [])
_forms_plugins.setdefault('auto-include', False)
PLUGINS[PLUGIN_FORMS] = _forms_plugins

# Take advantage of plugin system for Leaflet.MiniMap
if app_settings.get('MINIMAP'):
    PLUGINS['minimap'] = {
        'css': 'leaflet/Control.MiniMap.css',
        'js': 'leaflet/Control.MiniMap.js',
        'auto-include': True
    }


def _normalize_plugins_config():
    """
    Normalizes the PLUGINS setting:
        * ensures the 'css' and 'js' are arrays of URLs
        * ensures all URLs are transformed as follows:
            ** if the URL is absolute - leave it as-is
            ** if the URL is a root URL - starts with a / - leave it as-is
            ** the the URL is not a root URL - does not start with / - prepend settings.STATIC_URL
    Also, adds a special key - ALL - that includes 'css' and 'js' for all plugins listed
    """
    if '__is_normalized__' in PLUGINS:  # already normalized
        return

    listed_plugins = list(PLUGINS.keys())
    PLUGINS[PLUGINS_DEFAULT] = OrderedDict()
    PLUGINS[PLUGIN_ALL] = OrderedDict()

    RESOURCE_TYPE_KEYS = ['css', 'js']

    for key in listed_plugins:
        plugin_dict = PLUGINS[key]

        for resource_type in RESOURCE_TYPE_KEYS:
            # normalize the resource URLs
            urls = plugin_dict.get(resource_type, None)
            if isinstance(urls, str):
                urls = [urls]
            elif isinstance(urls, tuple):  # force to list
                urls = list(urls)
            elif isinstance(urls, list):  # already a list
                pass
            else:  # css/js has not been specified or the wrong type
                urls = []

            # normalize the URLs - see the docstring for details
            for i, url in enumerate(urls):
                if isinstance(url, Promise):
                    # If it is a Promise, then we have already
                    # seen this url and have lazily applied the `static` call
                    # to it, so we can safely skip the check below.
                    continue
                url_parts = urlparse(url)
                if url_parts.scheme or url_parts.path.startswith('/'):
                    # absolute URL or a URL starting at root
                    pass
                else:
                    # pass relative URL through django.contrib.staticfiles
                    urls[i] = lazy(static, str)(url)  # lazy variant of `static(url)`

            plugin_dict[resource_type] = urls

            # Append it to the DEFAULT pseudo-plugin if auto-include
            if plugin_dict.get('auto-include', False):
                PLUGINS[PLUGINS_DEFAULT].setdefault(resource_type, []).extend(urls)

            # also append it to the ALL pseudo-plugin;
            PLUGINS[PLUGIN_ALL].setdefault(resource_type, []).extend(urls)

    PLUGINS['__is_normalized__'] = True

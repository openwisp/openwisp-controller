from django.apps import AppConfig
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

from . import settings as app_settings
from . import theme
from .checks import admin_theme_settings_checks
from .menu import register_menu_group


def _staticfy(value):
    """Backard compatible call to static().

    Allows to keep backward compatibility with instances of OpenWISP which
    were using the previous implementation of OPENWISP_ADMIN_THEME_LINKS
    and OPENWISP_ADMIN_THEME_JS which didn't automatically pre-process
    those lists of static files with django.templatetags.static.static()
    and hence were not configured to allow those files to be found by the
    staticfile loaders, if static() raises ValueError, we assume one of
    either cases:

    1. An old instance has upgraded and we keep returning the old value so
    the file will continue being found although unprocessed by django's
    static file machinery.

    2. The value passed is wrong, instead of failing loudly we fail
    silently.
    """
    try:
        return static(value)
    # maintain backward compatibility
    except ValueError:
        return value


class OpenWispAdminThemeConfig(AppConfig):
    app_label = "openwisp_admin"
    name = "openwisp_utils.admin_theme"

    def ready(self):
        admin_theme_settings_checks(self)
        self.register_menu_groups()
        self.modify_admin_theme_settings_links()
        # monkey patch django.contrib.admin.apps.AdminConfig.default_site
        # in order to supply our customized admin site class
        # this is necessary in order to avoid having to modify
        # many other openwisp modules and repos
        from django.contrib import admin

        admin.apps.AdminConfig.default_site = app_settings.ADMIN_SITE_CLASS

    def register_menu_groups(self):
        # register dashboard item
        register_menu_group(
            position=10,
            config={"label": _("Home"), "url": "/admin", "icon": "ow-dashboard-icon"},
        )
        register_menu_group(
            position=899,
            config={
                "label": _("System info"),
                "url": "/admin/openwisp-system-info/",
                "icon": "ow-info-icon",
            },
        )

    def modify_admin_theme_settings_links(self):
        link_files = []
        for link_file in theme.THEME_LINKS:
            href = link_file["href"]
            href = href.replace("/static/", "")
            link_file["href"] = _staticfy(href)
            link_files.append(link_file)

        js_files = []
        for js_file in theme.THEME_JS:
            js_file = js_file.replace("/static/", "")
            js_files.append(_staticfy(js_file))

        theme.THEME_LINKS = link_files
        theme.THEME_JS = js_files

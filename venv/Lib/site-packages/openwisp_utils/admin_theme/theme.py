from django.core.exceptions import ImproperlyConfigured

from . import settings as app_settings

THEME_LINKS = app_settings.OPENWISP_ADMIN_THEME_LINKS.copy()
THEME_JS = app_settings.OPENWISP_ADMIN_THEME_JS.copy()


def register_theme_link(links):
    if not isinstance(links, list):
        raise ImproperlyConfigured(
            '"openwisp_utils.admin_theme.theme.register_theme_link"'
            ' accepts "list" of links'
        )
    for link in links:
        if link in THEME_LINKS:
            raise ImproperlyConfigured(
                f'{link["href"]} is already present in OPENWISP_ADMIN_THEME_LINKS'
            )
        THEME_LINKS.append(link)


def unregister_theme_link(links):
    if not isinstance(links, list):
        raise ImproperlyConfigured(
            '"openwisp_utils.admin_theme.theme.unregister_theme_link"'
            ' accepts "list" of links'
        )
    for link in links:
        try:
            THEME_LINKS.remove(link)
        except ValueError:
            raise ImproperlyConfigured(
                f'{link["href"]} was not added to OPENWISP_ADMIN_THEME_LINKS'
            )


def register_theme_js(jss):
    if not isinstance(jss, list):
        raise ImproperlyConfigured(
            '"openwisp_utils.admin_theme.theme.register_theme_js"'
            ' accepts "list" of JS'
        )
    for js in jss:
        if js in THEME_JS:
            raise ImproperlyConfigured(
                f"{js} is already present in OPENWISP_ADMIN_THEME_JS"
            )
        THEME_JS.append(js)


def unregister_theme_js(jss):
    if not isinstance(jss, list):
        raise ImproperlyConfigured(
            '"openwisp_utils.admin_theme.theme.unregister_theme_js"'
            ' accepts "list" of JS'
        )
    for js in jss:
        try:
            THEME_JS.remove(js)
        except ValueError:
            raise ImproperlyConfigured(f"{js} was not added to OPENWISP_ADMIN_THEME_JS")

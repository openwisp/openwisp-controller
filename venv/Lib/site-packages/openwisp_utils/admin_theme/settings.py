from django.conf import settings

ADMIN_SITE_CLASS = getattr(
    settings,
    "OPENWISP_ADMIN_SITE_CLASS",
    "openwisp_utils.admin_theme.admin.OpenwispAdminSite",
)

OPENWISP_ADMIN_THEME_LINKS = getattr(settings, "OPENWISP_ADMIN_THEME_LINKS", [])
OPENWISP_ADMIN_THEME_JS = getattr(settings, "OPENWISP_ADMIN_THEME_JS", [])
ADMIN_DASHBOARD_ENABLED = getattr(settings, "OPENWISP_ADMIN_DASHBOARD_ENABLED", True)

OPENWISP_EMAIL_LOGO = getattr(
    settings,
    "OPENWISP_EMAIL_LOGO",
    "https://raw.githubusercontent.com/openwisp/openwisp-utils/master/openwisp_utils/"
    "static/openwisp-utils/images/openwisp-logo.png",
)

OPENWISP_HTML_EMAIL = getattr(settings, "OPENWISP_HTML_EMAIL", True)
AUTOCOMPLETE_FILTER_VIEW = getattr(
    settings,
    "OPENWISP_AUTOCOMPLETE_FILTER_VIEW",
    "openwisp_utils.admin_theme.views.AutocompleteJsonView",
)

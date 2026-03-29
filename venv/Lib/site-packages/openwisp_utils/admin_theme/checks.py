from django.core.checks import Error, register

from . import settings as app_settings


@register()
def admin_theme_settings_checks(app_configs, **kwargs):
    errors = []
    links_error = False
    for item in app_settings.OPENWISP_ADMIN_THEME_LINKS:
        if not isinstance(item, dict):
            links_error = True
            break
        if any(["rel" not in item, "type" not in item, "href" not in item]):
            links_error = True
            break
    if links_error:
        errors.append(
            Error(
                msg="Invalid item: {}".format(item),
                hint="OPENWISP_ADMIN_THEME_LINKS should be a list of dictionaries, "
                "each dictionary must contain the following keys: rel, type and href.",
                obj="OPENWISP_ADMIN_THEME_LINKS",
            )
        )

    is_list_of_str = all(
        isinstance(item, str) for item in app_settings.OPENWISP_ADMIN_THEME_JS
    )
    if not isinstance(app_settings.OPENWISP_ADMIN_THEME_JS, list) or not is_list_of_str:
        errors.append(
            Error(
                msg="Improperly Configured",
                hint="OPENWISP_ADMIN_THEME_JS should be a list of strings.",
                obj="OPENWISP_ADMIN_THEME_JS",
            )
        )
    return errors

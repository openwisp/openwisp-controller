import logging
import sys

from django.apps import registry
from django.conf import settings
from django.urls import reverse

from ..admin_theme.menu import build_menu_groups
from . import theme


def menu_groups(request):
    menu = build_menu(request)
    if menu and sys.argv[1:2] != ["test"]:
        logging.warning(
            "register_menu_items is deprecated. Please update to use register_menu_group"
        )
    menu_groups = build_menu_groups(request)
    return {
        "openwisp_menu_items": menu,
        "openwisp_menu_groups": menu_groups,
        "show_userlinks_block": getattr(
            settings, "OPENWISP_ADMIN_SHOW_USERLINKS_BLOCK", False
        ),
    }


def build_menu(request):
    default_items = getattr(settings, "OPENWISP_DEFAULT_ADMIN_MENU_ITEMS", [])
    custom_items = getattr(settings, "OPENWISP_ADMIN_MENU_ITEMS", [])
    items = custom_items or default_items
    menu = []
    # loop over each item to build the menu
    # and check user has permission to see each item
    for item in items:
        app_label, model = item["model"].split(".")
        model_class = registry.apps.get_model(app_label, model)
        model_label = model.lower()
        url = reverse(f"admin:{app_label}_{model_label}_changelist")
        label = item.get("label", model_class._meta.verbose_name_plural)
        view_perm = f"{app_label}.view_{model_label}"
        change_perm = f"{app_label}.change_{model_label}"
        user = request.user
        if user.has_perm(view_perm) or user.has_perm(change_perm):
            menu.append({"url": url, "label": label, "class": model_label})
    return menu


def admin_theme_settings(request):
    return {
        "OPENWISP_ADMIN_THEME_LINKS": theme.THEME_LINKS,
        "OPENWISP_ADMIN_THEME_JS": theme.THEME_JS,
    }


# Kept for backward compatibility
# Todo: remove in version 0.9.0
menu_items = menu_groups

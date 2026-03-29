import importlib.metadata
import platform
from collections import OrderedDict

import distro
from django.conf import settings
from django.utils.module_loading import import_string

EXTRA_OPENWISP_PACKAGES = ["netdiff", "netjsonconfig"]


def get_installed_openwisp_packages():
    dists = importlib.metadata.distributions()
    return {
        dist.name: dist.version
        for dist in dists
        if dist.name is not None
        and (dist.name.startswith("openwisp") or dist.name in EXTRA_OPENWISP_PACKAGES)
    }


def _get_openwisp2_detail(attribute_name, fallback=None):
    try:
        return import_string(f"openwisp2.{attribute_name}")
    except ImportError:
        return fallback


def get_openwisp_version():
    return _get_openwisp2_detail("__openwisp_version__")


def get_openwisp_installation_method():
    return _get_openwisp2_detail("__openwisp_installation_method__", "unspecified")


def get_enabled_openwisp_modules():
    enabled_packages = {}
    installed_packages = get_installed_openwisp_packages()
    extra_packages = {}
    for package, version in installed_packages.items():
        if package in EXTRA_OPENWISP_PACKAGES:
            extra_packages[package] = version
            continue
        package_name = package.replace("-", "_")
        if package_name in settings.INSTALLED_APPS:
            enabled_packages[package] = version
        else:
            # check for sub-apps
            for app in settings.INSTALLED_APPS:
                if app.startswith(package_name + "."):
                    enabled_packages[package] = version
                    break
    enabled_packages = OrderedDict(sorted(enabled_packages.items()))
    enabled_packages.update(OrderedDict(sorted(extra_packages.items())))
    return enabled_packages


def get_os_details():
    uname = platform.uname()
    os_name = distro.name(pretty=True)
    # Simplify kernel version (e.g., "5.15.0-164-generic" -> "5.15.0")
    kernel_version = uname.release.split("-")[0]
    return {
        "os_version": os_name,
        "kernel_version": kernel_version,
        "hardware_platform": uname.machine,
    }

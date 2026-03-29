from collections import OrderedDict
from copy import deepcopy

import requests
from django.conf import settings
from django.utils.crypto import get_random_string
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SortedOrderedDict(OrderedDict):
    def update(self, items):
        super().update(items)
        temp = deepcopy(self)
        temp = sorted((temp.items()), key=lambda x: x[0])
        self.clear()
        super().update(temp)


def get_random_key():
    """generates a random string of 32 characters."""
    return get_random_string(length=32)


def register_menu_items(items, name_menu="OPENWISP_DEFAULT_ADMIN_MENU_ITEMS"):
    if not hasattr(settings, name_menu):
        setattr(settings, name_menu, items)
    else:
        current_menu = getattr(settings, name_menu)
        current_menu += items


def deep_merge_dicts(dict1, dict2):
    """Performs a deep merge of two dictionaries dict1 and dict2.

    Returns a new dict which is the result of the merge of the two dicts,
    all elements are deepcopied to avoid modifying the original data
    structures.
    """
    result = deepcopy(dict1)
    for key, value in dict2.items():
        if isinstance(value, dict):
            node = result.get(key, {})
            result[key] = deep_merge_dicts(node, value)
        else:
            result[key] = deepcopy(value)
    return result


def default_or_test(value, test):
    return value if not getattr(settings, "TESTING", False) else test


def print_color(string, color_name, end="\n"):
    """Prints colored output on terminal from a selected range of colors.

    If color_name is not present then output won't be colored.
    """
    color_dict = {
        "white_bold": "37;1",
        "green_bold": "32;1",
        "yellow_bold": "33;1",
        "red_bold": "31;1",
        "reset": "0",
    }
    color = color_dict.get(color_name, "0")
    print(f"\033[{color}m{string}\033[0m", end=end)


def retryable_request(
    method,
    timeout=(4, 8),
    max_retries=3,
    backoff_factor=1,
    backoff_jitter=0.0,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"),
    retry_kwargs=None,
    **kwargs,
):
    retry_kwargs = retry_kwargs or {}
    retry_kwargs.update(
        dict(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=allowed_methods,
            backoff_jitter=backoff_jitter,
        )
    )
    request_session = requests.Session()
    retries = Retry(**retry_kwargs)
    request_session.mount("https://", HTTPAdapter(max_retries=retries))
    request_session.mount("http://", HTTPAdapter(max_retries=retries))
    request_method = getattr(request_session, method)
    return request_method(timeout=timeout, **kwargs)

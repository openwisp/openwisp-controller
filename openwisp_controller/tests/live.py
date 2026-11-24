from functools import partial

from daphne.testing import DaphneProcess
from django.conf import settings


def _get_application(get_application, overrides):
    # Apply the overrides for this child process before Django loads middleware.
    for name, value in overrides.items():
        setattr(settings, name, value)
    return get_application()


def make_server_process(host, get_application, *, setup, overrides):
    return DaphneProcess(
        host,
        partial(_get_application, get_application, overrides),
        setup=setup,
    )

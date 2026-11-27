from functools import partial

from daphne.testing import DaphneProcess
from django.conf import settings


def _get_application(get_application, overrides):
    # Apply the overrides for this child process before Django loads middleware.
    for name, value in overrides.items():
        setattr(settings, name, value)
    return get_application()


def _setup(setup, initialize):
    setup()
    initialize()


def make_server_process(
    host, get_application, *, setup, overrides=None, initialize=None
):
    if overrides is not None:
        get_application = partial(_get_application, get_application, overrides)
    if initialize is not None:
        setup = partial(_setup, setup, initialize)
    return DaphneProcess(host, get_application, setup=setup)

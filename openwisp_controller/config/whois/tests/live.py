from contextlib import contextmanager
from functools import partial
from unittest.mock import patch

from ....tests.live import make_server_process


@contextmanager
def override_whois_configured(configured):
    from ... import settings as app_settings
    from ..handlers import override_whois_handlers

    with patch.object(
        app_settings, "WHOIS_CONFIGURED", configured
    ), override_whois_handlers(configured):
        yield


def _get_application(get_application, configured):
    # The child imports this callback before Django has initialized its settings.
    from ... import settings as app_settings

    app_settings.WHOIS_CONFIGURED = configured
    return get_application()


def make_whois_server_process(
    host, get_application, *, setup, configured, overrides=None
):
    return make_server_process(
        host,
        partial(_get_application, get_application, configured),
        setup=setup,
        overrides=overrides,
    )

from contextlib import ExitStack, contextmanager
from functools import partial
from unittest.mock import patch

from ....tests.live import make_server_process


@contextmanager
def override_whois_configured(configured):
    from ... import settings as app_settings
    from ..handlers import _whois_receivers, connect_whois_handlers

    with patch.object(
        app_settings, "WHOIS_CONFIGURED", configured
    ), ExitStack() as stack:
        # The test process has already run AppConfig.ready(). Preserve whatever
        # registrations were present before entering this test class.
        for signal, receiver, sender, uid in _whois_receivers():
            if signal.disconnect(sender=sender, dispatch_uid=uid):
                stack.callback(
                    signal.connect, receiver, sender=sender, dispatch_uid=uid
                )
            stack.callback(signal.disconnect, sender=sender, dispatch_uid=uid)
        connect_whois_handlers()
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

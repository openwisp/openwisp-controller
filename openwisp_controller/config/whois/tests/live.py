from functools import partial

from daphne.testing import DaphneProcess


def _setup_whois(setup, configured):
    # The child imports this callback before Django has initialized its settings.
    from ... import settings as app_settings

    setup()
    app_settings.WHOIS_CONFIGURED = configured


def make_whois_server_process(host, get_application, *, setup, configured):
    return DaphneProcess(
        host,
        get_application,
        setup=partial(_setup_whois, setup, configured),
    )

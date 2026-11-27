from contextlib import contextmanager

SCOPED_ORGANIZATION_ID = "11111111-1111-1111-1111-111111111111"
DEFAULT_ORGANIZATION_ID = "22222222-2222-2222-2222-222222222222"

_DEFAULT_COMMANDS = ("custom", "reboot", "change_password")
_SCOPED_COMMANDS = {
    SCOPED_ORGANIZATION_ID: (*_DEFAULT_COMMANDS, "uci_show"),
    DEFAULT_ORGANIZATION_ID: _DEFAULT_COMMANDS,
}


def _register_uci_show():
    # Daphne imports this module before the Django app registry is populated.
    from ..commands import COMMANDS, register_command
    from .utils import _uci_show_command_callable

    if "uci_show" in COMMANDS:
        return False
    register_command(
        "uci_show",
        {
            "label": "UCI show",
            "schema": {
                "title": "UCI show",
                "type": "object",
                "required": ["config"],
                "properties": {
                    "config": {
                        "type": "string",
                        "title": "Config",
                        "minLength": 1,
                        "pattern": ".",
                    }
                },
                "message": "Config cannot be empty.",
                "additionalProperties": False,
            },
            "callable": _uci_show_command_callable,
        },
    )
    return True


def register_scoped_commands():
    from ..commands import configure_organization_commands

    _register_uci_show()
    configure_organization_commands(_SCOPED_COMMANDS)


@contextmanager
def override_scoped_commands():
    from ..commands import override_organization_commands, unregister_command

    registered = _register_uci_show()
    try:
        with override_organization_commands(_SCOPED_COMMANDS):
            yield
    finally:
        if registered:
            unregister_command("uci_show")

SCOPED_ORGANIZATION_ID = "11111111-1111-1111-1111-111111111111"
DEFAULT_ORGANIZATION_ID = "22222222-2222-2222-2222-222222222222"


def register_scoped_commands():
    # Daphne imports this callback before the Django app registry is populated.
    from ..commands import (
        COMMANDS,
        ORGANIZATION_COMMAND_SCHEMA,
        ORGANIZATION_ENABLED_COMMANDS,
        register_command,
    )
    from .utils import _uci_show_command_callable

    registered = "uci_show" not in COMMANDS
    if registered:
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
    default_commands = ("custom", "reboot", "change_password")
    ORGANIZATION_ENABLED_COMMANDS[SCOPED_ORGANIZATION_ID] = (
        *default_commands,
        "uci_show",
    )
    ORGANIZATION_ENABLED_COMMANDS[DEFAULT_ORGANIZATION_ID] = default_commands
    for organization_id in (SCOPED_ORGANIZATION_ID, DEFAULT_ORGANIZATION_ID):
        ORGANIZATION_COMMAND_SCHEMA[organization_id] = {
            command: COMMANDS[command]["schema"]
            for command in ORGANIZATION_ENABLED_COMMANDS[organization_id]
        }
    return registered

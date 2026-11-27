from collections import OrderedDict
from contextlib import ExitStack, contextmanager

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from jsonschema import Draft4Validator

from .settings import ORGANIZATION_ENABLED_COMMANDS, USER_COMMANDS

DEFAULT_COMMANDS = OrderedDict(
    (
        (
            "custom",
            {
                "label": _("Custom commands"),
                "schema": {
                    "title": _("Custom"),
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "minLength": 1,
                            "title": _("Command"),
                            "pattern": ".",
                        },
                    },
                    "message": _("Command cannot be empty."),
                    "required": ["command"],
                    "additionalProperties": False,
                },
            },
        ),
        (
            "reboot",
            {
                "label": _("Reboot"),
                "schema": {
                    "title": _("Reboot"),
                    "type": "null",
                    "additionalProperties": False,
                },
            },
        ),
        (
            "change_password",
            {
                "label": _("Change password"),
                "schema": {
                    "title": _("Change Password"),
                    "type": "object",
                    "required": ["password", "confirm_password"],
                    "properties": {
                        "password": {
                            "$ref": "#/definitions/password_regex",
                            "title": _("Password"),
                        },
                        "confirm_password": {
                            "$ref": "#/definitions/password_regex",
                            "title": _("Confirm Password"),
                        },
                    },
                    "message": _("Your password must be at least 6 characters long"),
                    "additionalProperties": False,
                    "definitions": {
                        "password_regex": {
                            "type": "string",
                            "minLength": 6,
                            "maxLength": 30,
                            "pattern": r"[\S]",
                        }
                    },
                },
            },
        ),
    )
)
COMMANDS = DEFAULT_COMMANDS.copy()

COMMAND_CHOICES = [
    (command, command_config["label"]) for command, command_config in COMMANDS.items()
]
ORGANIZATION_COMMAND_SCHEMA = {}


def get_command_schema(command):
    try:
        return COMMANDS[command]["schema"]
    except KeyError:
        raise ImproperlyConfigured(f"No such Command, {command}")


def get_command_callable(command):
    try:
        return COMMANDS[command]["callable"]
    except KeyError:
        raise ImproperlyConfigured(f"No such Command, {command}")


def _validate_command(command_config):
    options = command_config.keys()
    assert "label" in options
    assert "schema" in options
    assert "callable" in options
    Draft4Validator(command_config["schema"])


def register_command(command_name, command_config):
    """
    Registers a new command.
    register_command(str,dict)
    """
    if not isinstance(command_name, str):
        raise ImproperlyConfigured("Command name should be type `str`.")
    if not isinstance(command_config, dict):
        raise ImproperlyConfigured("Command configuration should be type `dict`.")
    if command_name in COMMANDS:
        raise ImproperlyConfigured(f"{command_name} is an already registered Command.")

    _validate_command(command_config)
    COMMANDS.update({command_name: command_config})
    _register_command_choice(command_name, command_config)


def unregister_command(command_name):
    if not isinstance(command_name, str):
        raise ImproperlyConfigured("Command name should be type `str`")
    if command_name not in COMMANDS:
        raise ImproperlyConfigured(f"No such Command, {command_name}")

    COMMANDS.pop(command_name)
    _unregister_command_choice(command_name)


def _register_command_choice(command_name, command_config):
    label = command_config.get("label", command_name)
    COMMAND_CHOICES.append((command_name, label))


def _unregister_command_choice(command):
    for index, (key, name) in enumerate(COMMAND_CHOICES):
        if key == command:
            COMMAND_CHOICES.pop(index)
            return
    raise ImproperlyConfigured(f"No such Command choice {command}")


def configure_organization_commands(commands_by_org):
    """Update enabled commands and their schemas together during process setup."""
    enabled = {
        org: tuple(COMMANDS) if commands == "*" else commands
        for org, commands in commands_by_org.items()
    }
    schemas = {
        org: OrderedDict((name, COMMANDS[name]["schema"]) for name in commands)
        for org, commands in enabled.items()
    }
    ORGANIZATION_ENABLED_COMMANDS.update(enabled)
    ORGANIZATION_COMMAND_SCHEMA.update(schemas)


@contextmanager
def override_organization_commands(commands_by_org):
    """Temporarily configure commands and restore the affected organizations."""
    with ExitStack() as stack:
        for registry in (ORGANIZATION_ENABLED_COMMANDS, ORGANIZATION_COMMAND_SCHEMA):
            for org in commands_by_org:
                if org in registry:
                    stack.callback(registry.__setitem__, org, registry[org])
                else:
                    stack.callback(registry.pop, org, None)
        configure_organization_commands(commands_by_org)
        yield


for command_name, command_config in USER_COMMANDS:
    register_command(command_name, command_config)

configure_organization_commands(ORGANIZATION_ENABLED_COMMANDS)


def get_command_choices():
    """
    Returns the command choices.
    """
    return COMMAND_CHOICES

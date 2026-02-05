"""
Pytest configuration for openwisp_controller.

This module patches Django's transaction.on_commit to execute callbacks immediately
during tests. This is necessary because pytest-django's transaction=True marks tests
to run inside a transaction that gets rolled back, so on_commit callbacks never fire.
"""


def pytest_configure():
    """
    Patch transaction.on_commit to execute callbacks immediately during tests.
    This needs to be done after Django is configured but before tests run.
    """
    # Patch the transaction.on_commit in the connection base models module
    # This is where _schedule_command uses it
    from openwisp_controller.connection.base import models

    models.transaction.on_commit = lambda func, using=None: func()

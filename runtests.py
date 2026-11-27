#!/usr/bin/env python

"""Run the CI suites or a validated focused Django test."""

import os
import subprocess
import sys

import pytest

from openwisp_utils.test.runner import (
    InvalidTestArgument,
    compile_test_label_pattern,
    parse_test_arguments,
    validate_test_labels,
)


def run_focused_tests(arguments):
    import django

    sample_modules = tuple(
        f"openwisp2.sample_{name}.tests"
        for name in ("config", "connection", "geo", "pki", "subnet_division", "users")
    )
    pattern = compile_test_label_pattern(
        module_roots=(
            "openwisp_controller.tests",
            "openwisp_controller.config.tests",
            "openwisp_controller.connection.tests",
            "openwisp_controller.geo.tests",
            "openwisp_controller.pki.tests",
            "openwisp_controller.subnet_division.tests",
        ),
        exact_modules=sample_modules,
    )
    try:
        labels, flags = parse_test_arguments(
            arguments, pattern, ("--failfast", "--noinput"), require_label=True
        )
        sample_labels = [
            label for label in labels if label.group("module") in sample_modules
        ]
        if sample_labels and len(sample_labels) != len(labels):
            raise InvalidTestArgument(
                "Unsupported test argument: run sample app tests separately"
            )
        if sample_labels:
            os.environ["SAMPLE_APP"] = "1"
        os.environ["TESTING"] = "1"
        os.environ["DJANGO_SETTINGS_MODULE"] = "openwisp2.settings"
        sys.path.insert(0, "tests")
        sys.argv[1:] = ["test", *(label.group(0) for label in labels), *flags]
        django.setup()
        validate_test_labels(labels)
    except InvalidTestArgument as error:
        print(error, file=sys.stderr)
        return 2
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
    return 0


def run_tests(extra_args, settings_module, test_app):
    """
    Run Django tests with the specified settings module in a separate subprocess.
    """
    args = [
        "./tests/manage.py",
        "test",
        test_app,
        "--settings",
        settings_module,
        "--pythonpath",
        "tests",
    ]
    args.extend(extra_args)
    if os.environ.get("COVERAGE_RUN", False):
        # Since the Django tests are run in a separate process (using subprocess),
        # we need to run coverage in the subprocess as well.
        args = ["coverage", "run"] + args
    result = subprocess.run(args)
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--focused"]:
        sys.exit(run_focused_tests(sys.argv[2:]))

    # Configure Django settings for test execution
    # (sets Celery to eager mode, configures in-memory channels layer, etc.)
    os.environ.setdefault("TESTING", "1")
    args = sys.argv.copy()[1:]
    exclude_pytest = "--exclude-pytest" in args
    if exclude_pytest:
        args.pop(args.index("--exclude-pytest"))
    # normal tests vs SAMPLE_APP
    if not os.environ.get("SAMPLE_APP", False):
        test_app = "openwisp_controller"
        app_dir = "openwisp_controller/"
    else:
        test_app = "openwisp2"
        app_dir = "tests/openwisp2/"
        args += ["--exclude-tag", "slow"]
    # Run Django tests
    django_tests = run_tests(args, "openwisp2.settings", test_app)
    # Run pytest tests
    if not exclude_pytest:
        # Used to test django-channels
        sys.exit(pytest.main([app_dir]))
    else:
        sys.exit(django_tests)

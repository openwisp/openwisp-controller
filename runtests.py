#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

import pytest


def run_tests(extra_args, settings_module, test_app):
    """
    Run Django tests with the specified settings module in a separate subprocess.
    """
    args = [
        './tests/manage.py',
        'test',
        test_app,
        '--settings',
        settings_module,
        '--pythonpath',
        'tests',
    ]
    args.extend(extra_args)
    if os.environ.get('COVERAGE_RUN', False):
        # Since the Django tests are run in a separate process (using subprocess),
        # we need to run coverage in the subprocess as well.
        args = ['coverage', 'run'] + args
    result = subprocess.run(args)
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == '__main__':
    # Configure Django settings for test execution
    # (sets Celery to eager mode, configures in-memory channels layer, etc.)
    os.environ.setdefault('TESTING', '1')
    base_args = sys.argv.copy()[1:]
    if not os.environ.get('SAMPLE_APP', False):
        test_app = 'openwisp_controller'
        app_dir = 'openwisp_controller/'
    else:
        test_app = 'openwisp2'
        app_dir = 'tests/openwisp2/'
    # Run all tests except Selenium tests using SQLite
    sqlite_args = ['--exclude-tag', 'selenium_tests'] + base_args
    run_tests(sqlite_args, 'openwisp2.settings', test_app)

    # Run Selenium tests using PostgreSQL
    psql_args = [
        '--tag',
        'db_tests',
        '--tag',
        'selenium_tests',
    ] + base_args
    run_tests(psql_args, 'openwisp2.postgresql_settings', test_app)

    # Run pytest tests
    sys.exit(pytest.main([app_dir]))

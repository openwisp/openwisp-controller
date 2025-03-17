#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

import pytest


def run_tests(args, settings_module):
    """
    Run Django tests with the specified settings module in a separate subprocess.
    Executes the command inside the 'tests/' directory.
    """
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module
    result = subprocess.run(['python', 'manage.py'] + args, cwd='tests')
    if result.returncode != 0:
        sys.exit(result.returncode)  # Exit immediately if tests fail


if __name__ == '__main__':
    base_args = sys.argv.copy()[1:]
    if not os.environ.get('SAMPLE_APP', False):
        test_app = 'openwisp_controller'
        app_dir = 'openwisp_controller/'
    else:
        test_app = 'openwisp2'
        app_dir = 'tests/openwisp2/'
    # Run all tests except Selenium tests using SQLite
    sqlite_args = ['test', test_app, '--exclude-tag', 'selenium_tests'] + base_args
    run_tests(sqlite_args, 'openwisp2.settings')

    # Run Selenium tests using PostgreSQL
    psql_args = [
        'test',
        test_app,
        '--tag',
        'db_tests',
        '--tag',
        'selenium_tests',
    ] + base_args
    run_tests(psql_args, 'openwisp2.postgresql_settings')

    # Run pytest tests
    sys.path.insert(0, 'tests')
    sys.exit(pytest.main([app_dir]))

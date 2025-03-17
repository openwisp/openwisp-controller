#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

import pytest
from django.core.management import execute_from_command_line


def run_tests(args, settings_module):
    """
    Run Django tests with the specified settings module.
    """
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module
    execute_from_command_line(args)


if __name__ == '__main__':
    sys.path.insert(0, 'tests')

    args = sys.argv
    args.insert(1, 'test')
    if not os.environ.get('SAMPLE_APP', False):
        args.insert(2, 'openwisp_controller')
        app_dir = 'openwisp_controller/'
    else:
        args.insert(2, 'openwisp2')
        app_dir = 'tests/openwisp2/'

    # Run all tests except Selenium tests using SQLite
    sqlite_args = args.copy()
    sqlite_args.extend(['--exclude-tag', 'selenium_tests'])
    run_tests(sqlite_args, settings_module='openwisp2.settings')

    # Run Selenium tests using PostgreSQL
    psql_args = args.copy()
    psql_args.extend(['--tag', 'selenium_tests', '--tag', 'db_tests'])
    run_tests(psql_args, settings_module='openwisp2.postgresql_settings')

    sys.exit(pytest.main([app_dir]))

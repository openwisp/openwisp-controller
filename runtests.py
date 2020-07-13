#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

if __name__ == '__main__':
    sys.path.insert(0, 'tests')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openwisp2.settings')
    from django.core.management import execute_from_command_line

    args = sys.argv
    args.insert(1, 'test')
    if not os.environ.get('SAMPLE_APP', False):
        args.insert(2, 'openwisp_controller')
    else:
        args.insert(2, 'openwisp2')
    execute_from_command_line(args)
    if not os.environ.get('SAMPLE_APP', False):
        file_name = 'openwisp_controller/geo/tests'
    else:
        file_name = 'tests/openwisp2/sample_geo'
    return_code = subprocess.call(
        'pytest --cov=openwisp_controller --cov-append '
        f'-c tests/pytest.ini {file_name}',
        shell=True,
    )
    sys.exit(return_code)

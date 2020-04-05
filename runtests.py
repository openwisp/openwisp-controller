#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

if __name__ == '__main__':
    os.system('pytest -c pytest.ini')
    sys.path.insert(0, 'tests')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openwisp2.settings')
    from django.core.management import execute_from_command_line

    args = sys.argv
    args.insert(1, 'test')
    args.insert(2, 'openwisp_controller')
    execute_from_command_line(args)

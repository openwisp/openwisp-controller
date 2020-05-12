#!/bin/bash
set -e

pip install -U https://github.com/openwisp/django-netjsonconfig/tarball/master#egg=django_netjsonconfig
pip install -U https://github.com/openwisp/openwisp-utils/tarball/master#egg=openwisp_utils[qa]

#!/bin/bash
# called from Pipfile
pipenv run pip install --upgrade https://github.com/openwisp/django-netjsonconfig/tarball/master
pipenv run pip install --upgrade https://github.com/openwisp/openwisp-utils/tarball/master#egg=openwisp_utils[qa]

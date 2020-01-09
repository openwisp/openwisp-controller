#!/bin/bash
# called from Pipfile
pipenv run pip install https://github.com/openwisp/django-netjsonconfig/tarball/master
pipenv run pip install --upgrade "openwisp-utils[qa]>=0.3.2,<0.4.0"

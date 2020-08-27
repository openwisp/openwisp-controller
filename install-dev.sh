#!/bin/bash
set -e
# TODO: can be remove when openwisp-users 0.4.1 is released
# Commit needed for failures in tests:
# https://github.com/openwisp/openwisp-users/commit/ef347927136ddb4676479cb54cdc7cd08049e2e5
pip install -U --no-deps https://github.com/openwisp/openwisp-users/tarball/master

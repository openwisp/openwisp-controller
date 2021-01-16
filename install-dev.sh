#!/bin/bash
set -e

# TODO: Update URL before merging
pip install -U https://github.com/openwisp/openwisp-utils/tarball/dashboard#egg=openwisp-utils[rest,qa] --no-cache-dir

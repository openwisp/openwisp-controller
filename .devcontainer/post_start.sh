#!/bin/bash

# This script will run after the container is created
# It is an anti-pattern to install software here; rather please do
# any software installation in the Dockerfile (preferred) or in the post_create.sh script.
# Read more https://containers.dev/implementors/json_reference/#lifecycle-scripts

echo "Running post-start shell script"

# Examples to start up your service:
# npm start
sudo service redis-server start

cd /workspace/tests || exit
/bin/bash ./docker-entrypoint.sh

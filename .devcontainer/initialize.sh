#!/bin/bash

# A command string or list of command arguments to run on the host machine
# before the container is created.
# ⚠️ The command is run wherever the source code is located on the host.
# For cloud services, this is in the cloud.
# Read more https://containers.dev/implementors/json_reference/#lifecycle-scripts

echo "Running initialize commands"

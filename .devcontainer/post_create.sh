#!/bin/bash

# This command is the last of three that finalizes container setup when a dev container is created.
# Runs after updateContentCommand and after the dev container has been assigned to a user for the first time.
# You can use this to install software specific to the container user.

# Read more https://containers.dev/implementors/json_reference/#lifecycle-scripts
echo "Running post-create shell script"

GIT_EMAIL=""
GIT_USERNAME=""

[ -z "$GIT_EMAIL" ] && echo "Error: set your git email then rebuild the container" && exit 1
[ -z "$GIT_USERNAME" ] && echo "Error: set your git user name then rebuild the container" && exit 1
# Setup git
git config --global user.email "$GIT_EMAIL"
git config --global user.name "$GIT_USERNAME"

# Setup aliases
# echo "alias buildall='/workspace/buildbot/buildall.sh'" >> ~/.bashrc

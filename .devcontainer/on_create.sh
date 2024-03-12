#!/bin/sh

# This command is the first of three (along with updateContentCommand and postCreateCommand)
# that finalizes container setup when a dev container is created. It and subsequent commands
# execute inside the container immediately after it has started for the first time.
# Cloud services can use this command when caching or prebuilding a container.
# This means that it will not typically have access to user-scoped assets or secrets.
# Read more https://containers.dev/implementors/json_reference/#lifecycle-scripts

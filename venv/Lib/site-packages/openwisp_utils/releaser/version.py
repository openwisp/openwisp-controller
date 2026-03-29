import json
import re
import sys

import questionary


def get_current_version(config):
    # Parses the CURRENT_VERSION which comes from the version_path file
    # Returns the version string (e.g., "1.2.0") or None if CURRENT_VERSION is not set.
    current_version = config.get("CURRENT_VERSION")
    if not current_version:
        # Return None if CURRENT_VERSION is missing, allowing the main script to handle it
        return None, None
    try:
        major, minor, patch = (
            current_version[0],
            current_version[1],
            current_version[2],
        )
        version_type = current_version[3] if len(current_version) > 3 else "final"
        return f"{major}.{minor}.{patch}", version_type
    except IndexError:
        raise RuntimeError(
            f"The VERSION tuple {current_version} does not appear to have at least three elements."
        )


def _bump_with_regex(content, pattern, replacement, version_path, error_msg):
    """Helper to bump version using regex substitution."""
    new_content, count = re.subn(
        pattern,
        replacement,
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        raise RuntimeError(f"Failed to find and bump {error_msg} in {version_path}.")
    return new_content


def _bump_python_version(content, new_version, version_path):
    """Handles version bumping for Python packages."""
    major, minor, patch = new_version.split(".")
    new_tuple_string = f'({major}, {minor}, {patch}, "final")'
    return _bump_with_regex(
        content,
        r"^VERSION\s*=\s*\(.*\)",
        f"VERSION = {new_tuple_string}",
        version_path,
        "VERSION tuple",
    )


def _bump_npm_version(content, new_version, version_path):
    """Handles version bumping for NPM packages."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON in {version_path}: {e}") from e
    data["version"] = new_version
    return json.dumps(data, indent=2) + "\n"


def _bump_docker_version(content, new_version, version_path):
    """Handles version bumping for Docker packages."""
    return _bump_with_regex(
        content,
        r"^OPENWISP_VERSION\s*=\s*[^\s]+",
        f"OPENWISP_VERSION = {new_version}",
        version_path,
        "OPENWISP_VERSION",
    )


def _bump_ansible_version(content, new_version, version_path):
    """Handles version bumping for Ansible packages."""
    return _bump_with_regex(
        content,
        r'^__openwisp_version__\s*=\s*["\']([^"\']+)["\']',
        f'__openwisp_version__ = "{new_version}"',
        version_path,
        "__openwisp_version__",
    )


def _bump_openwrt_version(content, new_version, version_path):
    """Handles version bumping for OpenWRT packages."""
    return f"{new_version}\n"


# Maps package types to their version bump handlers
VERSION_BUMP_HANDLERS = {
    "python": _bump_python_version,
    "npm": _bump_npm_version,
    "docker": _bump_docker_version,
    "ansible": _bump_ansible_version,
    "openwrt": _bump_openwrt_version,
}


def bump_version(config, new_version):
    """Updates the VERSION tuple. Returns True on success, False if version_path is not configured."""
    version_path = config.get("version_path")
    package_type = config.get("package_type")
    if not version_path:
        # version bumping was not performed
        return False
    try:
        new_version_parts = new_version.split(".")
        if len(new_version_parts) != 3:
            raise ValueError("Version must be in the format X.Y.Z")
    except ValueError as e:
        print(f"Error: Invalid version format. {e}", file=sys.stderr)
        sys.exit(1)
    with open(version_path, "r") as f:
        content = f.read()
    handler = VERSION_BUMP_HANDLERS.get(package_type)
    if not handler:
        raise RuntimeError(f"Unknown package type: {package_type}")
    new_content = handler(content, new_version, version_path)
    with open(version_path, "w") as f:
        f.write(new_content)
    return True


def determine_new_version(current_version_str, current_type, is_bugfix):
    """Automatically determines the new version based on the current version and branch."""
    if not current_version_str:
        return questionary.text(
            "Could not determine the current version. Please enter the new version:"
        ).ask()

    major, minor, patch = map(int, current_version_str.split("."))

    if current_type != "final":
        # If the current version is not final, suggest the same version
        suggested_version = f"{major}.{minor}.{patch}"
    elif is_bugfix:
        # Bump patch for bugfix branches
        suggested_version = f"{major}.{minor}.{patch + 1}"
    else:
        # Bump minor for main branches
        suggested_version = f"{major}.{minor + 1}.0"

    print(f"\nSuggesting new version: {suggested_version}")
    use_suggested = questionary.confirm(
        "Do you want to use this version?", default=True
    ).ask()

    if use_suggested:
        return suggested_version
    else:
        return questionary.text("Please enter the desired version:").ask()

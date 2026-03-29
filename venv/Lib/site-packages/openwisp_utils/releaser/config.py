import ast
import json
import os
import re
import subprocess


def get_package_name_from_setup():
    """Parses setup.py to find the package name without raising an error."""
    if not os.path.exists("setup.py"):
        return None

    with open("setup.py", "r") as f:
        content = f.read()
        match = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", content)
        if match:
            return match.group(1)
    return None


def get_package_type_from_setup():
    """Detects package type based on config files present in the project."""
    package_type_files = {
        "setup.py": "python",
        "package.json": "npm",
        "docker-compose.yml": "docker",
        ".ansible-lint": "ansible",
        ".luacheckrc": "openwrt",
    }
    for filename, package_type in package_type_files.items():
        if os.path.exists(filename):
            return package_type
    return None


def detect_changelog_style(changelog_path):
    # Detects if the changelog uses the 'Version ' prefix for its entries
    if not os.path.exists(changelog_path):
        return True
    with open(changelog_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Look for a line that starts with 'Version X.Y.Z'
    if re.search(r"^Version\s+\d+\.\d+\.\d+", content, re.MULTILINE):
        return True
    # Look for a line that starts with just 'X.Y.Z'
    if re.search(r"^\d+\.\d+\.\d+", content, re.MULTILINE):
        return False
    # Default to True if no version entries are found yet
    return True


def _handle_python_version(config):
    """Handles version detection for Python packages."""
    project_name = get_package_name_from_setup()
    if not project_name:
        return
    package_directory = project_name.replace("-", "_")
    init_py_path = os.path.join(package_directory, "__init__.py")
    if not os.path.exists(init_py_path):
        return
    with open(init_py_path, "r") as f:
        content = f.read()
        version_match = re.search(r"^VERSION\s*=\s*\((.*)\)", content, re.M)
        if version_match:
            config["version_path"] = init_py_path
            try:
                version_tuple = ast.literal_eval(f"({version_match.group(1)})")
                config["CURRENT_VERSION"] = list(version_tuple)
            except (ValueError, SyntaxError):
                config["CURRENT_VERSION"] = None


def _handle_npm_version(config):
    """Handles version detection for NPM packages."""
    if not os.path.exists("package.json"):
        return
    with open("package.json", "r") as f:
        content = json.load(f)
        version_str = content.get("version")
        if not version_str:
            return
        config["version_path"] = "package.json"
        try:
            if "-" in version_str:
                version_tuple, version_type = version_str.split("-", 1)
            elif "_" in version_str:
                version_tuple, version_type = version_str.split("_", 1)
            else:
                version_tuple, version_type = version_str, "final"
            parts = version_tuple.split(".")
            if len(parts) != 3:
                raise ValueError(
                    f"Version '{version_str}' does not have expected 3 parts (X.Y.Z)"
                )
            config["CURRENT_VERSION"] = [
                int(parts[0]),
                int(parts[1]),
                int(parts[2]),
                version_type,
            ]
        except (ValueError, SyntaxError):
            config["CURRENT_VERSION"] = None


def _handle_docker_version(config):
    """Handles version detection for Docker packages."""
    if not os.path.exists("Makefile"):
        return
    with open("Makefile", "r") as f:
        content = f.read()
        version_match = re.search(
            r"^OPENWISP_VERSION\s*=\s*([^\s]+)", content, re.MULTILINE
        )
        if not version_match:
            return
        config["version_path"] = "Makefile"
        try:
            version_str = version_match.group(1)
            parts = version_str.split(".")
            if len(parts) != 3:
                raise ValueError(
                    f"Version '{version_str}' does not have expected 3 parts (X.Y.Z)"
                )
            config["CURRENT_VERSION"] = [
                int(parts[0]),
                int(parts[1]),
                int(parts[2]),
                "final",
            ]
        except (ValueError, SyntaxError):
            config["CURRENT_VERSION"] = None


def _handle_ansible_version(config):
    """Handles version detection for Ansible packages."""
    version_py_path = os.path.join("templates", "openwisp2", "version.py")
    if not os.path.exists(version_py_path):
        return
    with open(version_py_path, "r") as f:
        content = f.read()
        version_match = re.search(
            r"^__openwisp_version__\s*=\s*['\"]([^'\"]+)['\"]",
            content,
            re.MULTILINE,
        )
        if not version_match:
            return
        config["version_path"] = version_py_path
        try:
            version_str = version_match.group(1)
            parts = version_str.split(".")
            if len(parts) != 3:
                raise ValueError(
                    f"Version '{version_str}' does not have expected 3 parts (X.Y.Z)"
                )
            config["CURRENT_VERSION"] = [
                int(parts[0]),
                int(parts[1]),
                int(parts[2]),
                "final",
            ]
        except (ValueError, SyntaxError):
            config["CURRENT_VERSION"] = None


def _handle_openwrt_version(config):
    """Handles version detection for OpenWRT packages."""
    if not os.path.exists("VERSION"):
        return
    with open("VERSION", "r") as f:
        version_str = f.read().strip()
        if not version_str:
            return
        config["version_path"] = "VERSION"
        try:
            parts = version_str.split(".")
            if len(parts) != 3:
                raise ValueError(
                    f"Version '{version_str}' does not have expected 3 parts (X.Y.Z)"
                )
            config["CURRENT_VERSION"] = [
                int(parts[0]),
                int(parts[1]),
                int(parts[2]),
                "final",
            ]
        except (ValueError, SyntaxError):
            config["CURRENT_VERSION"] = None


# Maps package types to their version detection handlers
PACKAGE_VERSION_HANDLERS = {
    "python": _handle_python_version,
    "npm": _handle_npm_version,
    "docker": _handle_docker_version,
    "ansible": _handle_ansible_version,
    "openwrt": _handle_openwrt_version,
}


def load_config():
    """Loads configuration from project files and git."""
    config = {}

    try:
        origin_url = (
            subprocess.check_output(["git", "remote", "get-url", "origin"])
            .decode("utf-8")
            .strip()
        )
        repo_path = origin_url.removesuffix(".git").rstrip("/")
        # SSH URLs
        if repo_path.startswith("git@"):
            config["repo"] = repo_path.split(":")[-1]
        # HTTPS URLs
        else:
            config["repo"] = "/".join(repo_path.split("/")[-2:])
    except (subprocess.CalledProcessError, FileNotFoundError):
        config["repo"] = None
    config["version_path"] = None
    config["CURRENT_VERSION"] = None
    config["package_type"] = get_package_type_from_setup()
    # Use handler function if available for the detected package type
    handler = PACKAGE_VERSION_HANDLERS.get(config["package_type"])
    if handler:
        handler(config)

    possible_changelog_names = [
        "CHANGES.rst",
        "CHANGELOG.rst",
        "CHANGES.md",
        "CHANGELOG.md",
    ]
    found_changelog = None
    for name in possible_changelog_names:
        if os.path.exists(name):
            found_changelog = name
            break

    if found_changelog:
        config["changelog_path"] = found_changelog
        config["changelog_format"] = "md" if found_changelog.endswith(".md") else "rst"
    else:
        raise FileNotFoundError(
            "Error: Changelog file is required. Could not find CHANGES.rst, "
            "CHANGELOG.rst, CHANGES.md, or CHANGELOG.md."
        )

    config["changelog_uses_version_prefix"] = detect_changelog_style(
        config["changelog_path"]
    )

    return config

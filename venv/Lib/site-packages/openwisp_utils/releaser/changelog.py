import importlib.resources as pkg_resources
import os
import re
import subprocess
import sys
import tempfile

import questionary

from .utils import _call_docstrfmt


def find_cliff_config():
    # Locates the cliff.toml file packaged within 'openwisp_utils'.
    try:
        with pkg_resources.as_file(
            pkg_resources.files("openwisp_utils").joinpath("cliff.toml")
        ) as config_path:
            if os.path.exists(config_path):
                return str(config_path)
            else:
                return None
    except Exception as e:
        print("\n--- FATAL ERROR ---", file=sys.stderr)
        print(
            "Could not locate 'cliff.toml' inside the installed package.",
            file=sys.stderr,
        )
        print(f"The specific error was: {type(e).__name__}: {e}", file=sys.stderr)
        print("\n--- TROUBLESHOOTING ---", file=sys.stderr)
        print(
            "Ensure 'openwisp_utils' was installed correctly with the data file.",
            file=sys.stderr,
        )
        print("--------------------------\n", file=sys.stderr)
        return None


def run_git_cliff(version=None):
    """Runs the 'git cliff --unreleased' command and returns its output."""
    config_path = find_cliff_config()
    if not config_path:
        print(
            "Error: Path to cliff.toml was not found or provided.",
            file=sys.stderr,
        )
        sys.exit(1)
    # Pull latest tags before calculating changelog
    try:
        subprocess.run(
            ["git", "pull", "--tags"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to pull tags: {e.stderr}", file=sys.stderr)
    # Run git-cliff to calculate changelog
    try:
        cmd = ["git", "cliff", "--unreleased", "--config", config_path]
        if version:
            cmd.extend(["--tag", version])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except FileNotFoundError:
        print("Error: 'git' or 'git-cliff' command not found.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running 'git cliff': {e.stderr}", file=sys.stderr)
        sys.exit(1)


def process_changelog(changelog_text):
    """Processes raw changelog text to reorder and clean the Dependencies section."""
    lines = changelog_text.splitlines()

    # Iterate through the lines to find the start and end of the section
    # to isolate it for Dependency processing
    dep_start_index = -1
    dep_end_index = -1
    section_separator = ""

    for i, line in enumerate(lines):
        if line.strip() == "Dependencies":
            dep_start_index = i
            if i + 1 < len(lines):
                section_separator = lines[i + 1]
            continue

        # Dependencies section is over when we find the header for the next section
        if dep_start_index != -1 and i > dep_start_index + 1:
            stripped_line = line.strip()
            # Check if the line is a header section
            if (
                len(stripped_line) > 3
                and len(set(stripped_line)) == 1
                and stripped_line[0] in ["~", "+", "=", "-"]
            ):
                dep_end_index = i - 1
                break

    # If the file ends mid-section, mark the end right to the bottom
    if dep_start_index != -1 and dep_end_index == -1:
        dep_end_index = len(lines)

    # If no Dependencies section was found, just return
    if dep_start_index == -1:
        return changelog_text.strip()

    lines_before_deps = lines[:dep_start_index]
    dependency_lines_start = dep_start_index + 2
    dependency_lines = lines[dependency_lines_start:dep_end_index]
    lines_after_deps = lines[dep_end_index:]

    bumped_dependencies = {}
    other_dependencies = []

    # Regex to match dependency updates
    # 'Update [package] requirement from [old] to [new]'
    dep_update_pattern = re.compile(
        r"-\s*(?:Update|Bump)\s+`?`?([\w-]+)`?`?\s+requirement.*to\s+([~<>=!0-9a-zA-Z.,-]+)"
    )

    for line in dependency_lines:
        match = dep_update_pattern.search(line)
        if match:
            package_name = match.group(1)
            version_spec = match.group(2)
            final_version_spec = version_spec.split(",")[-1]
            bumped_dependencies[package_name] = (
                f"- Bumped ``{package_name}{final_version_spec}``"
            )
        else:
            if line.strip() and line not in other_dependencies:
                other_dependencies.append(line)

    final_lines = lines_before_deps
    final_lines.append(lines[dep_start_index])
    final_lines.append(section_separator)

    final_lines.extend(sorted(bumped_dependencies.values()))
    final_lines.extend(other_dependencies)

    # new line after Dependencies section
    if lines_after_deps:
        final_lines.append("")

    final_lines.extend(lines_after_deps)

    return "\n".join(final_lines)


def format_rst_block(content):
    """Formats a RST content using a temporary file."""
    temp_file_path = None
    header_for_formatting = "Changelog\n=========\n\n"
    content_with_header = header_for_formatting + content

    try:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".rst") as tf:
            temp_file_path = tf.name
            tf.write(content_with_header)

        _call_docstrfmt(temp_file_path)

        with open(temp_file_path, "r") as tf:
            formatted_full_content = tf.read()

        formatted_block = formatted_full_content.replace(
            header_for_formatting, "", 1
        ).strip()
        return formatted_block

    except subprocess.CalledProcessError as e:
        print(
            "\n❌ ERROR: Could not format changelog content with `docstrfmt`.",
            file=sys.stderr,
        )
        print("Linter output:", file=sys.stderr)
        indented_stderr = "\n".join(
            [f"    {line}" for line in e.stderr.strip().split("\n")]
        )
        print(indented_stderr, file=sys.stderr)
        print(
            "\nThis is likely due to a syntax error in the generated changelog from git-cliff."
        )
        decision = questionary.confirm(
            "Continue with the unformatted changelog? You can fix the syntax manually later.",
            default=True,
        ).ask()

        if decision:
            return content.strip()
        else:
            print("\n❌ Release process aborted by user.")
            sys.exit(1)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def get_release_block_from_file(config, version):
    """Reads the entire changelog file and extracts the block for a specific version."""
    changelog_path = config["changelog_path"]
    with open(changelog_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    release_lines = []
    in_release_block = False
    is_md = changelog_path.endswith(".md")
    # Adaptively add the 'Version ' prefix based on detected style
    prefix = "Version " if config.get("changelog_uses_version_prefix", True) else ""

    start_pattern = f"## {prefix}{version}" if is_md else f"{prefix}{version}"
    # This regex is used to find the next version header to know when to stop parsing
    next_version_regex_str = (
        rf"^## {re.escape(prefix)}\d+\.\d+\.\d+"
        if is_md
        else rf"^{re.escape(prefix)}\d+\.\d+\.\d+"
    )
    next_version_regex = re.compile(next_version_regex_str)

    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith(start_pattern):
            in_release_block = True
            release_lines.append(line)
            continue
        # Stop if we are in a block and find the next version header
        if in_release_block and next_version_regex.match(stripped_line):
            break
        if in_release_block:
            release_lines.append(line)

    return "".join(release_lines).strip() if release_lines else None


def update_changelog_file(changelog_path, new_block, is_port=False):
    # Updates the changelog file for all release types.
    # - For a feature release, it replaces the entire [Unreleased] section with the new content.
    # - For a ported bugfix, it inserts the new block after the [Unreleased] section.

    is_md = changelog_path.endswith(".md")
    try:
        with open(changelog_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Change log\n\n" if is_md else "Changelog\n=========\n\n"

    # Regex to find the entire [Unreleased] block, with optional "Version" prefix
    unreleased_block_regex_str = (
        r"^(##\s+(?:Version\s+)?\S+\s+\[Unreleased\](?:.|\n)*?)(?=\n##\s+(?:Version\s+)?|\Z)"
        if is_md
        else r"^((?:Version\s+)?\S+\s+\[Unreleased\]\n-+(?:.|\n)*?)(?=\n(?:Version\s+)?\d+\.\d+\.\d+\s+\[|\Z)"
    )
    unreleased_block_regex = re.compile(
        unreleased_block_regex_str, re.IGNORECASE | re.MULTILINE
    )
    unreleased_match = unreleased_block_regex.search(content)

    if not unreleased_match:
        # Fallback if no [Unreleased] section is found: insert after the main title.
        lines = content.splitlines(keepends=True)
        header_end_index = 1
        if len(lines) > 1 and ("===" in lines[1] or "---" in lines[1]):
            header_end_index = 2
        while len(lines) > header_end_index and not lines[header_end_index].strip():
            header_end_index += 1
        lines.insert(header_end_index, new_block.strip() + "\n\n")
        new_content = "".join(lines)
    elif is_port:
        # For a bugfix port, insert the new block AFTER the [Unreleased] block.
        insertion_point = unreleased_match.end()
        new_content = (
            content[:insertion_point].rstrip()
            + "\n\n"
            + new_block.strip()
            + "\n"
            + content[insertion_point:]
        )
    else:
        # For a feature release, REPLACE the entire [Unreleased] block.
        # We add a newline to the replacement to ensure there's a blank line
        # between the new block and the next version.
        replacement = new_block.strip() + "\n"
        new_content = unreleased_block_regex.sub(replacement, content, count=1)

    # Clean up any triple newlines to ensure clean formatting
    final_content = re.sub(r"\n\n\n+", "\n\n", new_content.strip()) + "\n"

    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write(final_content)

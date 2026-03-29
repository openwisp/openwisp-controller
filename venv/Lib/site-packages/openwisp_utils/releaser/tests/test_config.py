import pytest
from openwisp_utils.releaser.config import detect_changelog_style, load_config


@pytest.mark.parametrize(
    "changelog_filename, expected_format",
    [
        ("CHANGES.rst", "rst"),
        ("CHANGELOG.rst", "rst"),
        ("CHANGES.md", "md"),
        ("CHANGELOG.md", "md"),
    ],
)
def test_load_config_flexible_changelog_names(
    project_dir,
    create_setup_py,
    create_package_dir_with_version,
    create_changelog,
    init_git_repo,
    changelog_filename,
    expected_format,
):
    """Tests that various common changelog filenames are detected."""
    create_setup_py(project_dir)
    create_package_dir_with_version(project_dir)
    (project_dir / changelog_filename).write_text("Changelog")
    init_git_repo(project_dir)
    config = load_config()
    assert config["repo"] == "my-org/my-test-package"
    assert config["version_path"] == "my_test_package/__init__.py"
    assert config["CURRENT_VERSION"] == [1, 2, 3, "final"]
    assert config["changelog_path"] == changelog_filename
    assert config["changelog_format"] == expected_format


def test_load_config_raises_specific_error(project_dir, create_setup_py):
    create_setup_py(project_dir)
    with pytest.raises(FileNotFoundError, match="Could not find CHANGES.rst"):
        load_config()


def test_detect_changelog_style_with_prefix(tmp_path):
    """Tests that style is detected as 'True' when 'Version ' is present."""
    p = tmp_path / "CHANGES.rst"
    p.write_text("Version 1.0.0\n---\n- A change.")
    assert detect_changelog_style(str(p)) is True


def test_detect_changelog_style_without_prefix(tmp_path):
    """Tests that style is detected as 'False' when 'Version ' is absent."""
    p = tmp_path / "CHANGES.rst"
    p.write_text("1.0.0\n---\n- A change.")
    assert detect_changelog_style(str(p)) is False


def test_detect_changelog_style_empty_or_no_versions(tmp_path):
    """Tests that the style defaults to 'True' for new or empty files."""
    # File does not exist
    assert detect_changelog_style(str(tmp_path / "new.rst")) is True
    # File is empty
    p = tmp_path / "empty.rst"
    p.touch()
    assert detect_changelog_style(str(p)) is True
    # File has content but no versions
    p_content = tmp_path / "content.rst"
    p_content.write_text("Changelog\n=========")
    assert detect_changelog_style(str(p_content)) is True


def test_load_config_ssh_md(
    project_dir,
    create_setup_py,
    create_package_dir_with_version,
    create_changelog,
    init_git_repo,
):
    """Tests the ideal scenario with an SSH git remote and a .md changelog."""
    create_setup_py(project_dir)
    create_package_dir_with_version(project_dir)
    create_changelog(project_dir, "md")
    init_git_repo(project_dir, remote_url="git@github.com:my-org/my-test-package.git")
    config = load_config()
    assert config["repo"] == "my-org/my-test-package"
    assert config["changelog_path"] == "CHANGES.md"


def test_missing_changelog_raises_error(project_dir, create_setup_py, init_git_repo):
    """Verifies that a FileNotFoundError is raised if no changelog exists."""
    create_setup_py(project_dir)
    init_git_repo(project_dir)

    with pytest.raises(FileNotFoundError, match="Changelog file is required"):
        load_config()


def test_missing_setup_py_is_graceful(project_dir, create_changelog, init_git_repo):
    """Tests that if setup.py is missing, version info is None but other info is found."""
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["repo"] == "my-org/my-test-package"
    assert config["changelog_path"] == "CHANGES.rst"
    assert config["version_path"] is None
    assert config["CURRENT_VERSION"] is None


def test_missing_version_file_is_graceful(
    project_dir, create_setup_py, create_changelog
):
    """Tests that if __init__.py is missing, version info is None."""
    create_setup_py(project_dir)
    create_changelog(project_dir)
    config = load_config()
    assert config["version_path"] is None
    assert config["CURRENT_VERSION"] is None
    assert config["changelog_path"] == "CHANGES.rst"
    assert config["repo"] is None


def test_version_tuple_not_in_init_py(
    project_dir, create_setup_py, create_package_dir_with_version, create_changelog
):
    """Tests that if __init__.py exists but has no VERSION tuple, version info is None."""
    create_setup_py(project_dir)
    create_package_dir_with_version(project_dir, version_str="# This file is empty")
    create_changelog(project_dir)
    config = load_config()
    assert config["version_path"] is None
    assert config["CURRENT_VERSION"] is None
    assert config["changelog_path"] == "CHANGES.rst"


def test_get_package_name_no_match(project_dir):
    # Tests that get_package_name_from_setup returns None
    # if setup.py exists but the name attribute cannot be found.
    (project_dir / "setup.py").write_text("from setuptools import setup\nsetup()")
    from openwisp_utils.releaser.config import get_package_name_from_setup

    assert get_package_name_from_setup() is None


def test_config_malformed_version(
    project_dir, create_setup_py, create_package_dir_with_version, create_changelog
):
    """Tests config loading when __init__.py contains a malformed VERSION tuple."""
    create_setup_py(project_dir)
    create_package_dir_with_version(project_dir, version_str="VERSION = (1, 2,,")
    create_changelog(project_dir)
    config = load_config()
    assert config["CURRENT_VERSION"] is None


def test_config_malformed_version_literal_eval_fails(
    project_dir, create_setup_py, create_package_dir_with_version, create_changelog
):
    # Tests config loading when __init__.py contains a malformed VERSION
    # tuple that causes literal_eval to fail.

    create_setup_py(project_dir)
    # This string is valid python syntax but will fail literal_eval
    create_package_dir_with_version(
        project_dir, version_str="VERSION = (1, 2, 'a' + 'b')"
    )
    create_changelog(project_dir)
    config = load_config()
    # Should gracefully handle the error and return None
    assert config["CURRENT_VERSION"] is None


# NPM Package Tests
def test_npm_package_detection(
    project_dir, create_package_json, create_changelog, init_git_repo
):
    """Tests that npm package type is detected when package.json exists."""
    create_package_json(project_dir, version="1.2.3")
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "npm"
    assert config["version_path"] == "package.json"
    assert config["CURRENT_VERSION"] == [1, 2, 3, "final"]


def test_npm_package_with_prerelease_suffix(
    project_dir, create_package_json, create_changelog, init_git_repo
):
    """Tests npm package version parsing with prerelease suffix (e.g., 1.2.3-beta)."""
    create_package_json(project_dir, version="1.2.3-beta")
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "npm"
    assert config["CURRENT_VERSION"] == [1, 2, 3, "beta"]


def test_npm_package_with_underscore_suffix(
    project_dir, create_package_json, create_changelog, init_git_repo
):
    """Tests npm package version parsing with underscore suffix (e.g., 1.2.3_rc1)."""
    create_package_json(project_dir, version="1.2.3_rc1")
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "npm"
    assert config["CURRENT_VERSION"] == [1, 2, 3, "rc1"]


def test_npm_package_missing_version(project_dir, create_changelog, init_git_repo):
    """Tests that npm package handles missing version gracefully."""
    import json

    (project_dir / "package.json").write_text(json.dumps({"name": "test-package"}))
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "npm"
    assert config["version_path"] is None
    assert config["CURRENT_VERSION"] is None


def test_npm_package_invalid_version(
    project_dir, create_package_json, create_changelog, init_git_repo
):
    """Tests that npm package handles invalid version format gracefully."""
    create_package_json(project_dir, version="1.2")  # Invalid: only 2 parts
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "npm"
    assert config["version_path"] == "package.json"
    assert config["CURRENT_VERSION"] is None


# Docker Package Tests
def test_docker_package_detection(
    project_dir, create_docker_compose, create_makefile, create_changelog, init_git_repo
):
    """Tests that docker package type is detected when docker-compose.yml exists."""
    create_docker_compose(project_dir)
    create_makefile(project_dir, version="1.2.3")
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "docker"
    assert config["version_path"] == "Makefile"
    assert config["CURRENT_VERSION"] == [1, 2, 3, "final"]


def test_docker_package_without_makefile(
    project_dir, create_docker_compose, create_changelog, init_git_repo
):
    """Tests docker package without Makefile - version should be None."""
    create_docker_compose(project_dir)
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "docker"
    assert config["version_path"] is None
    assert config["CURRENT_VERSION"] is None


def test_docker_package_invalid_version(
    project_dir, create_docker_compose, create_changelog, init_git_repo
):
    """Tests docker package with invalid version in Makefile gracefully."""
    create_docker_compose(project_dir)
    (project_dir / "Makefile").write_text(
        "OPENWISP_VERSION = 1.2\n"
    )  # Invalid: only 2 parts
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "docker"
    assert config["version_path"] == "Makefile"
    assert config["CURRENT_VERSION"] is None


# Ansible Package Tests
def test_ansible_package_detection(
    project_dir,
    create_ansible_lint,
    create_ansible_version_file,
    create_changelog,
    init_git_repo,
):
    """Tests that ansible package type is detected when .ansible-lint exists."""
    create_ansible_lint(project_dir)
    create_ansible_version_file(project_dir, version="1.2.3")
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "ansible"
    assert config["version_path"] == "templates/openwisp2/version.py"
    assert config["CURRENT_VERSION"] == [1, 2, 3, "final"]


def test_ansible_package_without_version_file(
    project_dir, create_ansible_lint, create_changelog, init_git_repo
):
    """Tests ansible package without version file - version should be None."""
    create_ansible_lint(project_dir)
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "ansible"
    assert config["version_path"] is None
    assert config["CURRENT_VERSION"] is None


def test_ansible_package_malformed_version(
    project_dir, create_ansible_lint, create_changelog, init_git_repo
):
    """Tests ansible package with malformed version string gracefully."""
    create_ansible_lint(project_dir)
    templates_dir = project_dir / "templates" / "openwisp2"
    templates_dir.mkdir(parents=True, exist_ok=True)
    (templates_dir / "version.py").write_text('__openwisp_version__ = "not-a-version"')
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "ansible"
    assert config["version_path"] == "templates/openwisp2/version.py"
    assert config["CURRENT_VERSION"] is None


# OpenWRT Package Tests
def test_openwrt_package_detection(
    project_dir, create_luacheckrc, create_version_file, create_changelog, init_git_repo
):
    """Tests that openwrt package type is detected when .luacheckrc exists."""
    create_luacheckrc(project_dir)
    create_version_file(project_dir, version="1.2.3")
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "openwrt"
    assert config["version_path"] == "VERSION"
    assert config["CURRENT_VERSION"] == [1, 2, 3, "final"]


def test_openwrt_without_version_file(
    project_dir, create_luacheckrc, create_changelog, init_git_repo
):
    """Tests openwrt package without VERSION file."""
    create_luacheckrc(project_dir)
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "openwrt"
    assert config["version_path"] is None
    assert config["CURRENT_VERSION"] is None


def test_openwrt_invalid_version(
    project_dir, create_luacheckrc, create_changelog, init_git_repo
):
    """Tests openwrt package with invalid version format gracefully."""
    create_luacheckrc(project_dir)
    (project_dir / "VERSION").write_text("1.2")  # Invalid: only 2 parts
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "openwrt"
    assert config["version_path"] == "VERSION"
    assert config["CURRENT_VERSION"] is None


# Package Type Priority Tests
def test_package_type_priority_python_over_npm(
    project_dir,
    create_setup_py,
    create_package_dir_with_version,
    create_package_json,
    create_changelog,
    init_git_repo,
):
    """Tests that Python is detected first when both setup.py and package.json exist."""
    create_setup_py(project_dir)
    create_package_dir_with_version(project_dir)
    create_package_json(project_dir)
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] == "python"
    assert config["version_path"] == "my_test_package/__init__.py"


def test_no_package_type_detected(project_dir, create_changelog, init_git_repo):
    """Tests when no recognizable package type is found."""
    create_changelog(project_dir)
    init_git_repo(project_dir)
    config = load_config()
    assert config["package_type"] is None
    assert config["version_path"] is None
    assert config["CURRENT_VERSION"] is None

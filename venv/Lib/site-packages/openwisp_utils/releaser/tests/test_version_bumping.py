from unittest.mock import mock_open, patch

import pytest
from openwisp_utils.releaser.version import (
    bump_version,
    determine_new_version,
    get_current_version,
)

SAMPLE_INIT_FILE = """
# Some comments
VERSION = (1, 2, 0, "alpha")
# More comments
"""

EXPECTED_BUMPED_CONTENT = """
# Some comments
VERSION = (1, 2, 0, "final")
# More comments
"""


@pytest.fixture
def mock_config():
    return {"version_path": "path/__init__.py"}


@pytest.fixture
def mock_config_no_path():
    return {}


def test_get_current_version_success():
    """Tests get_current_version with CURRENT_VERSION set in config."""
    mock_config = {
        "version_path": "path/__init__.py",
        "CURRENT_VERSION": [1, 2, 0, "alpha"],
    }
    version, version_type = get_current_version(mock_config)
    assert version == "1.2.0"
    assert version_type == "alpha"


def test_get_current_version_no_path_in_config(mock_config_no_path):
    version, version_type = get_current_version(mock_config_no_path)
    assert version is None
    assert version_type is None


@patch("os.path.exists", return_value=False)
def test_get_current_version_file_not_found(_, mock_config):
    version, version_type = get_current_version(mock_config)
    assert version is None
    assert version_type is None


def test_bump_version_success(mock_config):
    mock_config["package_type"] = "python"
    m_open = mock_open(read_data=SAMPLE_INIT_FILE)
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open):
        result = bump_version(mock_config, "1.2.0")

    assert result is True
    written_content = m_open().write.call_args[0][0]
    expected_content = 'VERSION = (1, 2, 0, "final")'
    assert expected_content in written_content


def test_bump_version_no_path_in_config(mock_config_no_path):
    result = bump_version(mock_config_no_path, "1.2.0")
    assert result is False


def test_bump_version_file_not_found(mock_config):
    with patch("os.path.exists", return_value=False):
        with pytest.raises(FileNotFoundError):
            bump_version(mock_config, "1.2.0")


def test_get_current_version_no_tuple():
    """Tests that get_current_version returns None when CURRENT_VERSION is None."""
    mock_config = {"version_path": "path/__init__.py", "CURRENT_VERSION": None}
    version, version_type = get_current_version(mock_config)
    assert version is None
    assert version_type is None


def test_get_current_version_short_tuple():
    """Tests RuntimeError if VERSION tuple has fewer than three elements."""
    mock_config = {
        "version_path": "path/__init__.py",
        "CURRENT_VERSION": [1, 2],  # Only 2 elements
    }
    with pytest.raises(RuntimeError, match="does not appear to have at least three"):
        get_current_version(mock_config)


def test_bump_version_no_tuple_found(mock_config):
    """Tests RuntimeError during version bumping if VERSION is not found."""
    mock_config["package_type"] = "python"
    with patch("os.path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data="NO_VERSION_HERE")
    ):
        with pytest.raises(RuntimeError, match="Failed to find and bump VERSION"):
            bump_version(mock_config, "1.2.1")


def test_bump_version_invalid_format():
    """Tests the ValueError for an invalid version string in `bump_version`."""
    mock_config = {"version_path": "dummy/path.py"}

    with pytest.raises(SystemExit):
        bump_version(mock_config, "1.2")


@patch("openwisp_utils.releaser.version.questionary")
def test_determine_new_version_not_final(mock_questionary):
    """Tests the version suggestion when the current version is not 'final'."""
    mock_questionary.confirm.return_value.ask.return_value = True

    suggested = determine_new_version("1.2.0", "alpha", is_bugfix=False)

    assert suggested == "1.2.0"
    mock_questionary.confirm.assert_called_once_with(
        "Do you want to use this version?", default=True
    )


@patch("openwisp_utils.releaser.version.questionary")
def test_determine_new_version_bugfix_suggestion(mock_questionary):
    """Tests the version suggestion logic for a bugfix release."""
    mock_questionary.confirm.return_value.ask.return_value = True
    suggested = determine_new_version("1.2.3", "final", is_bugfix=True)
    assert suggested == "1.2.4"


@patch("openwisp_utils.releaser.version.questionary")
def test_determine_new_version_feature_suggestion(mock_questionary):
    """Tests the version suggestion logic for a feature release."""
    mock_questionary.confirm.return_value.ask.return_value = True
    suggested = determine_new_version("1.2.3", "final", is_bugfix=False)
    assert suggested == "1.3.0"


@patch("openwisp_utils.releaser.version.questionary")
def test_determine_new_version_user_provides_own(mock_questionary):
    """Tests the flow where the user rejects the suggested version."""
    # User rejects the suggestion
    mock_questionary.confirm.return_value.ask.return_value = False
    # User enters a custom version
    mock_questionary.text.return_value.ask.return_value = "2.0.0"

    version = determine_new_version("1.2.3", "final", is_bugfix=False)

    # The returned version should be the one entered by the user
    assert version == "2.0.0"


@patch("openwisp_utils.releaser.version.questionary")
def test_determine_new_version_prompts_when_current_version_is_none(mock_questionary):
    """Tests that user is prompted to enter version when current version cannot be determined.

    This covers the edge case for Ansible (and other) packages where the
    version file doesn't exist, resulting in CURRENT_VERSION being None.
    """
    mock_questionary.text.return_value.ask.return_value = "1.0.0"
    version = determine_new_version(None, None, is_bugfix=False)
    assert version == "1.0.0"
    mock_questionary.text.assert_called_once_with(
        "Could not determine the current version. Please enter the new version:"
    )
    # confirm should NOT be called since we skip the suggestion flow
    mock_questionary.confirm.assert_not_called()


# NPM Package Version Tests
def test_get_current_version_npm():
    """Tests getting current version from npm package.json."""
    config = {
        "package_type": "npm",
        "version_path": "package.json",
        "CURRENT_VERSION": [1, 2, 3, "final"],
    }
    version, version_type = get_current_version(config)
    assert version == "1.2.3"
    assert version_type == "final"


def test_get_current_version_npm_with_prerelease():
    """Tests getting current version from npm package with prerelease."""
    config = {
        "package_type": "npm",
        "version_path": "package.json",
        "CURRENT_VERSION": [1, 2, 3, "beta"],
    }
    version, version_type = get_current_version(config)
    assert version == "1.2.3"
    assert version_type == "beta"


def test_bump_version_npm():
    """Tests bumping version for npm packages in package.json."""
    config = {
        "package_type": "npm",
        "version_path": "package.json",
        "CURRENT_VERSION": [1, 2, 3, "beta"],
    }
    package_json_content = '{\n  "name": "test-package",\n  "version": "1.2.3-beta"\n}'
    m_open = mock_open(read_data=package_json_content)
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open):
        result = bump_version(config, "1.2.4")
    assert result is True
    written_content = m_open().write.call_args[0][0]
    assert '"version": "1.2.4"' in written_content


# Docker Package Version Tests
def test_get_current_version_docker():
    """Tests getting current version from docker Makefile."""
    config = {
        "package_type": "docker",
        "version_path": "Makefile",
        "CURRENT_VERSION": [1, 2, 3, "final"],
    }
    version, version_type = get_current_version(config)
    assert version == "1.2.3"
    assert version_type == "final"


def test_bump_version_docker():
    """Tests bumping version for docker packages in Makefile."""
    config = {
        "package_type": "docker",
        "version_path": "Makefile",
        "CURRENT_VERSION": [1, 2, 3, "final"],
    }
    makefile_content = "OPENWISP_VERSION = 1.2.3\nDOCKER_IMAGE = openwisp/test\n"
    m_open = mock_open(read_data=makefile_content)
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open):
        result = bump_version(config, "1.2.4")

    assert result is True
    written_content = m_open().write.call_args[0][0]
    assert "OPENWISP_VERSION = 1.2.4" in written_content


# Ansible Package Version Tests
def test_get_current_version_ansible():
    """Tests getting current version from ansible version.py."""
    config = {
        "package_type": "ansible",
        "version_path": "templates/openwisp2/version.py",
        "CURRENT_VERSION": [1, 2, 3, "final"],
    }
    version, version_type = get_current_version(config)
    assert version == "1.2.3"
    # Ansible versions are now stored with "final" in CURRENT_VERSION list
    assert version_type == "final"


def test_bump_version_ansible():
    """Tests bumping version for ansible packages in templates/openwisp2/version.py."""
    config = {
        "package_type": "ansible",
        "version_path": "templates/openwisp2/version.py",
        "CURRENT_VERSION": [1, 2, 3],
    }
    version_py_content = '__openwisp_version__ = "1.2.3"\n'
    m_open = mock_open(read_data=version_py_content)
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open):
        result = bump_version(config, "1.2.4")
    assert result is True
    written_content = m_open().write.call_args[0][0]
    assert '__openwisp_version__ = "1.2.4"' in written_content


# OpenWRT Agents Package Version Tests
def test_get_current_version_openwrt():
    """Tests getting current version from OpenWRT VERSION file."""
    config = {
        "package_type": "openwrt",
        "version_path": "VERSION",
        "CURRENT_VERSION": [1, 2, 3, "final"],
    }
    version, version_type = get_current_version(config)
    assert version == "1.2.3"
    assert version_type == "final"


def test_bump_version_openwrt():
    """Tests bumping version for OpenWRT in VERSION file."""
    config = {
        "package_type": "openwrt",
        "version_path": "VERSION",
        "CURRENT_VERSION": [1, 2, 3, "final"],
    }
    version_file_content = "1.2.3\n"
    m_open = mock_open(read_data=version_file_content)
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open):
        result = bump_version(config, "1.2.4")
    assert result is True
    written_content = m_open().write.call_args[0][0]
    assert "1.2.4" in written_content

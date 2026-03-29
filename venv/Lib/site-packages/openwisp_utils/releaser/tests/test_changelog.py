import os
import re
import shutil
import subprocess
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest
from openwisp_utils.releaser.changelog import (
    find_cliff_config,
    format_rst_block,
    get_release_block_from_file,
    process_changelog,
    run_git_cliff,
)
from openwisp_utils.releaser.release import main as run_release
from openwisp_utils.releaser.release import update_changelog_file


def find_changelog_test_cases():
    # Scans the samples directory to find matching pairs of commit
    # and changelog files to be used as test cases
    SAMPLES_DIR = "openwisp_utils/releaser/tests/samples"
    COMMIT_SAMPLES_DIR = os.path.join(SAMPLES_DIR, "commits")
    CHANGELOG_SAMPLES_DIR = os.path.join(SAMPLES_DIR, "changelogs")

    test_cases = []

    if not os.path.isdir(COMMIT_SAMPLES_DIR):
        return []

    for commit_filename in os.listdir(COMMIT_SAMPLES_DIR):
        if not commit_filename.endswith(".txt"):
            continue

        base_name = os.path.splitext(commit_filename)[0]
        changelog_filename = f"{base_name}.rst"

        commit_filepath = os.path.join(COMMIT_SAMPLES_DIR, commit_filename)
        changelog_filepath = os.path.join(CHANGELOG_SAMPLES_DIR, changelog_filename)

        if os.path.exists(changelog_filepath):
            # The 'id' gives a nice name to the test case when it runs
            test_cases.append(
                pytest.param(commit_filepath, changelog_filepath, id=base_name)
            )

    return test_cases


@pytest.fixture
def git_repo():
    # Sets up a temporary directory with a clean Git repository
    # and copies the cliff.toml file into it. It changes the current
    # working directory to the temp directory and cleans up everything
    # after the test is done.
    original_dir = os.getcwd()
    test_dir = tempfile.mkdtemp()

    # Copy the cliff.toml to the test directory
    cliff_toml_path = os.path.join(original_dir, "cliff.toml")
    if os.path.exists(cliff_toml_path):
        shutil.copy(cliff_toml_path, test_dir)

    os.chdir(test_dir)

    # Initialize Git repository
    subprocess.run(
        ["git", "init", "--initial-branch=main"], check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)

    # Yield control to the test function
    yield original_dir

    # Teardown: clean up after the test
    os.chdir(original_dir)
    shutil.rmtree(test_dir)


@pytest.mark.parametrize(
    "commit_file, expected_changelog_file", find_changelog_test_cases()
)
def test_changelog_generation(git_repo, commit_file, expected_changelog_file):
    """Tests changelog generation for all discovered sample files"""
    original_dir = git_repo
    commit_count = 0

    # Helper to create a file and commit it
    def _git_commit(message):
        nonlocal commit_count
        with open(f"file_{commit_count}.txt", "w") as f:
            f.write(f"This is file number {commit_count}")
        subprocess.run(["git", "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--file=-"],
            input=message.encode("utf-8"),
            check=True,
            capture_output=True,
        )
        commit_count += 1

    # Construct full paths to sample files from the original directory
    commit_file_path = os.path.join(original_dir, commit_file)
    expected_changelog_path = os.path.join(original_dir, expected_changelog_file)

    # Create commits from the provided sample file
    with open(commit_file_path, "r") as f:
        content = f.read()

    commit_messages = re.split(r"\n=======================================\n", content)
    commit_messages = [msg.strip() for msg in commit_messages if msg.strip()]

    for message in commit_messages:
        if message:
            _git_commit(message)

    # Read the expected output from the sample file
    with open(expected_changelog_path, "r") as f:
        expected_output = f.read().strip()

    # Generate the changelog and get the actual output
    raw_changelog = run_git_cliff()
    processed_changelog = process_changelog(raw_changelog)
    processed_changelog = "Changelog\n=========\n\n" + processed_changelog
    actual_output = format_rst_block(processed_changelog)

    assert actual_output == expected_output


@patch("openwisp_utils.releaser.changelog.find_cliff_config", return_value=None)
def test_run_git_cliff_no_config(mock_find_config):
    with pytest.raises(SystemExit):
        run_git_cliff()


@patch("openwisp_utils.releaser.changelog.find_cliff_config", return_value="path")
@patch("subprocess.run")
def test_run_git_cliff_file_not_found(mock_run, mock_find_config):
    # First call (git pull --tags) succeeds, second call (git cliff) raises FileNotFoundError
    mock_run.side_effect = [
        subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        FileNotFoundError,
    ]
    with pytest.raises(SystemExit):
        run_git_cliff()


@patch("openwisp_utils.releaser.changelog.find_cliff_config", return_value="path")
@patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd"))
def test_run_git_cliff_called_process_error(mock_run, mock_find_config):
    with pytest.raises(SystemExit):
        run_git_cliff()


@patch("openwisp_utils.releaser.changelog.questionary.confirm")
@patch("openwisp_utils.releaser.changelog.subprocess.run")
def test_format_rst_block_failure_user_continues(mock_subprocess, mock_questionary):
    """Tests that if formatting fails, the user can choose to continue with the unformatted content."""
    # Simulate user choosing to continue
    mock_questionary.return_value.ask.return_value = True
    # Simulate a docstrfmt failure
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        1, "docstrfmt", stderr="Syntax error on line 5."
    )
    original_content = "* a list"

    result = format_rst_block(original_content)

    # The function should return the original, unformatted content
    assert result == original_content
    # The user should have been prompted
    mock_questionary.assert_called_once()


@patch("openwisp_utils.releaser.changelog.questionary.confirm")
@patch("openwisp_utils.releaser.changelog.subprocess.run")
def test_format_rst_block_failure_user_aborts(mock_subprocess, mock_questionary):
    """Tests that if formatting fails, the user can choose to abort the release process."""
    # Simulate user choosing to abort
    mock_questionary.return_value.ask.return_value = False
    # Simulate a docstrfmt failure
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        1, "docstrfmt", stderr="Syntax error on line 5."
    )

    with pytest.raises(SystemExit):
        format_rst_block("* a list")

    # The user should have been prompted
    mock_questionary.assert_called_once()


@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="""
Changelog
=========

Version 1.2.0 [Unreleased]
--------------------------
- In progress.

Version 1.1.0
-------------
- A feature.
""",
)
def test_get_release_block_with_prefix(mock_file):
    """Test extracting a release block when 'Version ' prefix is used."""
    mock_config = {
        "changelog_path": "CHANGES.rst",
        "changelog_uses_version_prefix": True,
    }
    expected_block = "Version 1.1.0\n-------------\n- A feature."
    result = get_release_block_from_file(mock_config, "1.1.0")
    assert result == expected_block


@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="""
Changelog
=========

1.2.0 [Unreleased]
------------------
- In progress.

1.1.0
-----
- A feature.
""",
)
def test_get_release_block_without_prefix(mock_file):
    """Test extracting a release block when 'Version ' prefix is NOT used."""
    mock_config = {
        "changelog_path": "CHANGES.rst",
        "changelog_uses_version_prefix": False,
    }
    expected_block = "1.1.0\n-----\n- A feature."
    result = get_release_block_from_file(mock_config, "1.1.0")
    assert result == expected_block


SAMPLE_CHANGELOG = """Changelog
=========

Version 1.2.0 [Unreleased]
--------------------------

Work in progress.

Version 1.1.2 [2025-06-18]
--------------------------

- A previous fix.
"""

NEW_RELEASE_BLOCK = """Version 1.1.3  [2025-08-11]
---------------------------

Bugfixes
~~~~~~~~

- A critical bugfix.
"""


@patch("builtins.open", new_callable=mock_open, read_data=SAMPLE_CHANGELOG)
def test_update_changelog_bugfix_port_flow(mock_file):
    """Test that a ported bugfix release inserts content correctly."""

    update_changelog_file("CHANGES.rst", NEW_RELEASE_BLOCK, is_port=True)

    written_content = mock_file().write.call_args[0][0]

    assert NEW_RELEASE_BLOCK in written_content
    assert "Version 1.2.0 [Unreleased]" in written_content
    # New block should be after [Unreleased] and before the previous version
    assert written_content.find("Version 1.1.3") > written_content.find(
        "Version 1.2.0 [Unreleased]"
    )
    assert written_content.find("Version 1.1.3") < written_content.find("Version 1.1.2")
    # "Work in progress." text below unreleased header should come before new bugfix block
    assert written_content.find("Work in progress.") < written_content.find(
        "Version 1.1.3"
    )


@patch("builtins.open", new_callable=mock_open, read_data=SAMPLE_CHANGELOG)
def test_update_changelog_feature_flow(mock_file):
    """Test that a feature release REPLACES the unreleased block."""
    feature_release_block = NEW_RELEASE_BLOCK.replace("1.1.3", "1.2.0")

    update_changelog_file("CHANGES.rst", feature_release_block, is_port=False)

    written_content = mock_file().write.call_args[0][0]

    assert "Version 1.2.0" in written_content
    assert "Version 1.2.0 [Unreleased]" not in written_content
    assert "Version 1.1.2 [2025-06-18]" in written_content


@patch("openwisp_utils.releaser.changelog.pkg_resources.as_file")
def test_find_cliff_config_generic_exception(mock_as_file):
    """Tests the generic `Exception` block in `find_cliff_config`."""
    mock_as_file.side_effect = Exception("A generic error occurred")
    assert find_cliff_config() is None


@patch(
    "openwisp_utils.releaser.changelog.find_cliff_config",
    return_value="path/to/cliff.toml",
)
@patch("openwisp_utils.releaser.changelog.subprocess.run")
def test_run_git_cliff_with_version_tag(mock_subprocess_run, mock_find_config):
    """Tests the `--tag` argument extension in `run_git_cliff`."""
    mock_subprocess_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="Changelog content", stderr=""
    )
    run_git_cliff(version="1.0.0")
    executed_cmd = mock_subprocess_run.call_args[0][0]
    assert "--tag" in executed_cmd and "1.0.0" in executed_cmd


@patch(
    "openwisp_utils.releaser.changelog.find_cliff_config",
    return_value="path/to/cliff.toml",
)
@patch("openwisp_utils.releaser.changelog.subprocess.run")
def test_run_git_cliff_calls_git_pull_tags(mock_subprocess_run, mock_find_config):
    """Tests that `git pull --tags` is executed before running git-cliff."""
    # Mock the subprocess.run to return different results for different calls
    mock_subprocess_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="Changelog content", stderr=""
    )
    run_git_cliff()
    # Verify that subprocess.run was called twice: once for git pull --tags, once for git-cliff
    assert mock_subprocess_run.call_count == 2
    # Check the first call is for git pull --tags
    first_call_args = mock_subprocess_run.call_args_list[0][0][0]
    assert first_call_args == ["git", "pull", "--tags"]
    # Check the second call is for git cliff
    second_call_args = mock_subprocess_run.call_args_list[1][0][0]
    assert (
        "git" in second_call_args
        and "cliff" in second_call_args
        and "--unreleased" in second_call_args
    )


@patch(
    "openwisp_utils.releaser.changelog.find_cliff_config",
    return_value="path/to/cliff.toml",
)
@patch("openwisp_utils.releaser.changelog.subprocess.run")
@patch("builtins.print")
def test_run_git_cliff_git_pull_tags_fails(
    mock_print, mock_subprocess_run, mock_find_config
):
    """Tests that `git pull --tags` failure is handled gracefully and git-cliff still runs."""
    # First call (git pull --tags) fails, second call (git cliff) succeeds
    mock_subprocess_run.side_effect = [
        subprocess.CalledProcessError(1, "git pull --tags", stderr="Network error"),
        subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Changelog content", stderr=""
        ),
    ]
    run_git_cliff()
    # Verify that subprocess.run was called twice despite the first failure
    assert mock_subprocess_run.call_count == 2
    # Verify warning message was printed
    mock_print.assert_called_once()
    call_args = mock_print.call_args[0][0]
    assert "Warning: Failed to pull tags:" in call_args
    assert "Network error" in call_args


def test_process_changelog_dependencies_as_last_section():
    """Tests where 'Dependencies' is the last section."""
    changelog_text = (
        "Dependencies\n++++++++++++\n- Update `package-a` requirement to >=1.2.3"
    )
    processed_text = process_changelog(changelog_text)
    assert "- Bumped ``package-a>=1.2.3``" in processed_text


def test_update_changelog_no_unreleased_section_fallback():
    """Test the fallback logic when the '[Unreleased]' section is missing."""
    initial_content = (
        "Changelog\n=========\n\nVersion 1.0.0\n-------------\n- Initial release."
    )
    new_block = "Version 1.1.0\n-------------\n- New feature."
    with patch("builtins.open", mock_open(read_data=initial_content)) as m:
        update_changelog_file("CHANGES.rst", new_block)
        written_content = m().write.call_args[0][0]
        expected = (
            "Changelog\n=========\n\nVersion 1.1.0\n-------------\n- "
            "New feature.\n\nVersion 1.0.0\n-------------\n- Initial release.\n"
        )
        assert written_content == expected


def test_main_flow_no_changes_found(mock_all):
    """Tests when `git-cliff` returns nothing."""
    mock_all["run_git_cliff"].return_value = ""
    with pytest.raises(SystemExit):
        run_release()
    mock_all["print"].assert_any_call("No changes found for the new release. Exiting.")


@patch("openwisp_utils.releaser.changelog.pkg_resources.as_file")
def test_find_cliff_config_path_does_not_exist(mock_as_file):
    """Tests when the config file path exists in theory but not on disk."""
    mock_context_manager = MagicMock()
    mock_path = "/path/that/does/not/exist"
    mock_context_manager.__enter__.return_value = mock_path
    mock_context_manager.__exit__.return_value = None
    mock_as_file.return_value = mock_context_manager

    # Patch os.path.exists to return False for the simulated path
    with patch("os.path.exists", return_value=False) as mock_exists:
        result = find_cliff_config()
        assert result is None
        mock_exists.assert_called_with(mock_path)


def test_update_changelog_file_not_found():
    """Tests the behavior when the changelog file does not exist."""
    # Use a real temporary file to test the FileNotFoundError path
    temp_dir = tempfile.mkdtemp()
    changelog_path = os.path.join(temp_dir, "CHANGES.rst")
    new_block = "Version 1.0.0\n-------------\n- Initial release."

    # The file does not exist, so opening it for 'r' will fail,
    # triggering the 'except FileNotFoundError' block.
    update_changelog_file(changelog_path, new_block)

    with open(changelog_path, "r") as f:
        content = f.read()

    # Check that the file was created with default headers and the new block
    assert "Changelog\n=========\n\n" in content
    assert new_block in content
    shutil.rmtree(temp_dir)

from unittest.mock import MagicMock, patch

import pytest
from openwisp_utils.releaser.release import check_prerequisites
from openwisp_utils.releaser.release import main as run_release
from openwisp_utils.releaser.release import port_changelog_to_main
from openwisp_utils.releaser.utils import SkipSignal


def test_feature_release_flow_markdown(mock_all, mocker):
    """Tests the full release flow for a project using a Markdown changelog."""
    mock_config, mock_gh = mock_all["check_prerequisites"].return_value
    mock_config["changelog_path"] = "CHANGES.md"
    mock_config["changelog_format"] = "md"

    mock_all["get_release_block_from_file"].return_value = None

    mocker.patch(
        "openwisp_utils.releaser.release.rst_to_markdown",
        return_value="## Version 1.2.1\n## Markdown Changelog",
    )

    run_release()

    mock_all["update_changelog"].assert_called_once()
    mock_all["format_file"].assert_not_called()

    release_call_args = mock_gh.create_release.call_args.args
    assert "## Markdown Changelog" in release_call_args[2]


def test_release_flow_manual_bump(mock_all):
    """Tests the flow where automatic version bumping fails and the user is prompted to do it manually."""
    mock_all["bump_version"].return_value = False
    run_release()
    all_print_calls = "".join(str(c) for c in mock_all["print"].call_args_list)
    assert "The version number could not be bumped automatically" in all_print_calls
    mock_all["questionary_confirm"].assert_any_call(
        "Press Enter when you have bumped the version number..."
    )


def test_prerequisite_check_failure(mocker):
    """Tests that the script exits if the prerequisite check fails."""
    mocker.patch("openwisp_utils.releaser.release.shutil.which", return_value=None)
    mocker.patch(
        "openwisp_utils.releaser.release.load_config",
        return_value={"repo": "test/repo"},
    )
    mocker.patch(
        "openwisp_utils.releaser.release.GitHub.check_pr_creation_permission",
        return_value=(True, "Permissions OK"),
    )

    with pytest.raises(SystemExit):
        from openwisp_utils.releaser.release import check_prerequisites

        check_prerequisites()


def test_main_flow_user_cancels_version(mock_all):
    """Tests the flow where the user cancels when asked for a version."""
    mock_all["get_current_version"].return_value = (None, None)
    mock_all["questionary_text"].return_value.ask.return_value = (
        ""  # User presses enter
    )
    with pytest.raises(SystemExit):
        run_release()


def test_main_flow_user_rejects_changelog(mock_all):
    """Tests the flow where the user rejects the generated changelog."""
    mock_all["questionary_confirm"].return_value.ask.side_effect = [
        True,  # Use AI
        True,  # Use suggested version
        False,  # Reject changelog block
    ]
    with pytest.raises(SystemExit):
        run_release()


def test_bugfix_flow_skip_porting(mock_all):
    """Tests a full bugfix release but declines the final changelog porting step."""
    mock_all["_git_command_map"][
        ("git", "rev-parse", "--abbrev-ref", "HEAD")
    ].stdout = "1.1.x"
    mock_all["questionary_confirm"].return_value.ask.side_effect = [
        True,
        True,
        True,
        True,
        False,  # Decline porting
    ]
    run_release()
    mock_gh = mock_all["GitHub"].return_value
    assert mock_gh.create_pr.call_count == 1


def test_check_prerequisites_config_load_error(mocker):
    """Tests the FileNotFoundError when loading config."""
    mocker.patch("openwisp_utils.releaser.release.shutil.which", return_value=True)
    mocker.patch("os.environ.get", return_value="fake-token")
    mocker.patch(
        "openwisp_utils.releaser.release.load_config", side_effect=FileNotFoundError
    )
    with pytest.raises(SystemExit):
        check_prerequisites()


def test_check_prerequisites_github_permission_error(mocker):
    """Tests when the GitHub token does not have PR creation permissions."""
    mocker.patch("openwisp_utils.releaser.release.shutil.which", return_value=True)
    mocker.patch("os.environ.get", return_value="fake-token")
    mocker.patch(
        "openwisp_utils.releaser.release.load_config",
        return_value={"repo": "owner/repo"},
    )
    mock_gh = MagicMock()
    mock_gh.check_pr_creation_permission.return_value = (
        False,
        "Permission denied.",
    )
    mocker.patch("openwisp_utils.releaser.release.GitHub", return_value=mock_gh)
    with pytest.raises(SystemExit):
        check_prerequisites()


def test_check_prerequisites_success(mocker):
    """Tests the successful execution path of `check_prerequisites`."""
    mocker.patch("openwisp_utils.releaser.release.shutil.which", return_value=True)
    mocker.patch("os.environ.get", return_value="fake-token")
    mocker.patch(
        "openwisp_utils.releaser.release.load_config",
        return_value={"repo": "owner/repo"},
    )
    mock_gh = MagicMock()
    mock_gh.check_pr_creation_permission.return_value = (
        True,
        "Permissions verified.",
    )
    mocker.patch("openwisp_utils.releaser.release.GitHub", return_value=mock_gh)
    config, gh = check_prerequisites()
    assert config is not None and gh is not None


def test_main_flow_pr_merge_wait(mock_all):
    """Tests the `while` loop that waits for a PR to be merged."""
    mock_gh_instance = mock_all["GitHub"].return_value
    mock_gh_instance.is_pr_merged.side_effect = [False, True]
    run_release()
    mock_all["time"].assert_called_once_with(20)
    assert mock_gh_instance.is_pr_merged.call_count == 2


@patch("openwisp_utils.releaser.release.update_changelog_file")
@patch("openwisp_utils.releaser.release.format_file_with_docstrfmt")
@patch("openwisp_utils.releaser.release.subprocess.run")
@patch("openwisp_utils.releaser.release.questionary")
def test_port_changelog_to_main_flow(
    mock_questionary, mock_subprocess, mock_format_file, mock_update_changelog
):
    """Tests the changelog porting process for both RST and MD files, and the cancellation path."""
    mock_gh = MagicMock()
    mock_config_rst = {"changelog_path": "CHANGES.rst"}
    mock_questionary.select.return_value.ask.return_value = "main"
    port_changelog_to_main(mock_gh, mock_config_rst, "1.1.1", "- fix", "1.1.x")
    mock_gh.create_pr.assert_called_once()
    mock_format_file.assert_called_once_with("CHANGES.rst")

    mock_gh.reset_mock()

    # Test Cancellation path
    mock_questionary.select.return_value.ask.return_value = None
    port_changelog_to_main(mock_gh, mock_config_rst, "1.1.1", "- fix", "1.1.x")
    mock_gh.create_pr.assert_not_called()


def test_main_bugfix_flow_with_porting(mock_all, mocker):
    """Tests the main release flow for a bugfix, including accepting the changelog port."""
    mock_all["_git_command_map"][
        ("git", "rev-parse", "--abbrev-ref", "HEAD")
    ].stdout = "1.1.x"
    mock_all["questionary_confirm"].return_value.ask.return_value = True
    mock_porting_func = mocker.patch(
        "openwisp_utils.releaser.release.port_changelog_to_main"
    )
    run_release()
    mock_porting_func.assert_called_once()


def test_main_flow_no_version_prefix_style(mock_all):
    """Tests the release flow for a changelog that does NOT use the 'Version ' prefix."""
    # Config where the "Version" prefix is not used
    mock_config, _ = mock_all["check_prerequisites"].return_value
    mock_config["changelog_uses_version_prefix"] = False
    mock_all["get_release_block_from_file"].return_value = None

    run_release()

    # Check that the block written to the file does NOT have the "Version" prefix
    update_call_args = mock_all["update_changelog"].call_args[0]
    written_block = update_call_args[1]
    assert written_block.startswith("1.3.0")
    assert not written_block.startswith("Version 1.3.0")

    # Check that the user is shown the FULL block for approval
    full_print_output = "".join(str(call) for call in mock_all["print"].call_args_list)
    assert "The following block will be added to the changelog" in full_print_output
    # Verify the header shown to the user is also in the correct style
    assert "1.3.0  [2025-08-11]" in full_print_output
    assert "Version 1.3.0" not in full_print_output


def test_main_flow_skip_pr_creation(mock_all):
    """Tests the flow where user skips PR creation."""
    mock_gh = mock_all["GitHub"].return_value
    mock_gh.create_pr.side_effect = SkipSignal

    run_release()

    # Ensure the user is prompted to complete the step manually
    mock_all["questionary_confirm"].assert_any_call(
        "Press Enter when you have merged the PR manually."
    )
    # The rest of the flow should continue, so release creation should be attempted
    mock_gh.create_release.assert_called_once()


def test_main_flow_skip_release_creation(mock_all):
    """Tests the flow where user skips GitHub release creation."""
    mock_gh = mock_all["GitHub"].return_value
    mock_gh.create_release.side_effect = SkipSignal

    run_release()

    mock_gh.create_pr.assert_called_once()
    mock_all["questionary_confirm"].assert_any_call(
        "Press Enter when you have created the release manually."
    )


@patch("openwisp_utils.releaser.release.subprocess.run")
def test_port_changelog_to_main_flow_markdown(mock_subprocess, mock_all):
    """Tests the changelog porting process for a Markdown file."""
    mock_gh = MagicMock()
    mock_config_md = {"changelog_path": "CHANGES.md"}
    mock_all["questionary_select"].return_value.ask.return_value = "main"

    with patch("openwisp_utils.releaser.release.update_changelog_file") as mock_update:
        port_changelog_to_main(mock_gh, mock_config_md, "1.1.1", "- fix", "1.1.x")
        # Check that the header for markdown is correctly formatted
        called_with_content = mock_update.call_args[0][1]
        assert "## Version 1.1.1" in called_with_content


@patch("openwisp_utils.releaser.release.subprocess.run")
def test_port_changelog_skip_pr_creation(mock_subprocess, mock_all):
    """Tests skipping PR creation during changelog porting."""
    mock_gh = MagicMock()
    mock_gh.create_pr.side_effect = SkipSignal
    mock_config = {"changelog_path": "CHANGES.rst"}
    mock_all["questionary_select"].return_value.ask.return_value = "main"

    with patch("openwisp_utils.releaser.release.update_changelog_file"):
        port_changelog_to_main(mock_gh, mock_config, "1.1.1", "- fix", "1.1.x")
        mock_all["questionary_confirm"].assert_any_call(
            "Press Enter when you have created the PR manually."
        )

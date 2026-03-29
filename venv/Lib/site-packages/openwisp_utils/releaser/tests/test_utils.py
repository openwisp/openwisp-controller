import subprocess
from unittest.mock import MagicMock, patch

import pytest
import requests
from openwisp_utils.releaser.release import (
    adjust_markdown_headings,
    demote_markdown_headings,
    rst_to_markdown,
)
from openwisp_utils.releaser.utils import (
    SkipSignal,
    format_file_with_docstrfmt,
    retryable_request,
)

RST_SAMPLE = """
Features
~~~~~~~~

- A new feature.

Changes
~~~~~~~

Backward-incompatible changes
+++++++++++++++++++++++++++++

- A breaking change.
"""

MD_EXPECTED = """
### Features

- A new feature.

### Changes

#### Backward-incompatible changes

- A breaking change.
"""


def test_rst_to_markdown_conversion():
    """Test basic reStructuredText to Markdown conversion."""
    # Test that the function calls it correctly.
    with patch("pypandoc.convert_text", return_value="Converted") as mock_convert:
        result = rst_to_markdown(RST_SAMPLE)
        assert result == "Converted"
        mock_convert.assert_called_once()


def test_adjust_markdown_headings():
    """Test that markdown headings are correctly adjusted for the CHANGES.md file."""
    raw_md = """
## Features

- A feature.

## Changes

### Backward-incompatible changes

- A change.
"""
    expected_md = """
### Features

- A feature.

### Changes

#### Backward-incompatible changes

- A change.
"""
    result = adjust_markdown_headings(raw_md)
    assert result.strip() == expected_md.strip()


def test_demote_markdown_headings():
    """Test that markdown headings are correctly demoted for the GitHub release body."""
    input_md = """
### Features

- A feature.

#### Dependencies

- A dependency.
"""
    expected_md = """
# Features

- A feature.

## Dependencies

- A dependency.
"""
    result = demote_markdown_headings(input_md)
    assert result.strip() == expected_md.strip()


@patch("openwisp_utils.releaser.utils.subprocess.run")
@patch("builtins.print")
def test_format_file_with_docstrfmt_success(mock_print, mock_subprocess):
    """Tests the successful `format_file_with_docstrfmt` function."""
    file_path = "CHANGES.rst"
    format_file_with_docstrfmt(file_path)

    expected_command = [
        "docstrfmt",
        "--ignore-cache",
        "--section-adornments",
        "=-~+^\"'.:",
        "--line-length",
        "74",
        file_path,
    ]
    mock_subprocess.assert_called_once_with(
        expected_command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    mock_print.assert_called_once_with(f"✅ Formatted {file_path} successfully.")


@patch("openwisp_utils.releaser.utils.questionary.select")
@patch("openwisp_utils.releaser.utils.subprocess.run")
def test_format_file_interactive_retry_success(mock_subprocess, mock_questionary):
    # Tests the interactive retry loop in `format_file_with_docstrfmt`.
    # The first format attempt fails, the user "fixes" it, and the second succeeds.

    # First call fails, second call succeeds
    mock_subprocess.side_effect = [
        subprocess.CalledProcessError(1, "docstrfmt", stderr="Syntax error"),
        MagicMock(),  # Represents a successful run
    ]
    # User chooses to retry
    mock_questionary.return_value.ask.return_value = "I have fixed the file, try again."

    format_file_with_docstrfmt("CHANGES.rst")

    # subprocess.run should have been called twice
    assert mock_subprocess.call_count == 2
    mock_questionary.assert_called_once()


@patch("openwisp_utils.releaser.utils.questionary.select")
@patch("openwisp_utils.releaser.utils.subprocess.run")
def test_format_file_interactive_skip(mock_subprocess, mock_questionary):
    """Tests that the user can skip formatting in `format_file_with_docstrfmt`."""
    # The call to docstrfmt fails
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        1, "docstrfmt", stderr="Syntax error"
    )
    # User chooses to skip
    mock_questionary.return_value.ask.return_value = (
        "Skip formatting and continue with the unformatted file."
    )

    format_file_with_docstrfmt("CHANGES.rst")

    # subprocess.run should only have been called once
    assert mock_subprocess.call_count == 1
    mock_questionary.assert_called_once()


@patch("openwisp_utils.releaser.utils.questionary.select")
@patch("openwisp_utils.releaser.utils.subprocess.run")
def test_format_file_interactive_abort(mock_subprocess, mock_questionary):
    """Tests that the user can abort the release in `format_file_with_docstrfmt`."""
    # The call to docstrfmt fails
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        1, "docstrfmt", stderr="Syntax error"
    )
    # User chooses to abort
    mock_questionary.return_value.ask.return_value = "Abort the release process."

    with pytest.raises(SystemExit):
        format_file_with_docstrfmt("CHANGES.rst")

    # subprocess.run should have been called once before aborting
    assert mock_subprocess.call_count == 1
    mock_questionary.assert_called_once()


@patch("requests.request")
def test_retryable_request_success(mock_request):
    """Tests that the function returns a response on the first successful call."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    response = retryable_request(method="get", url="http://example.com")

    assert response == mock_response
    mock_request.assert_called_once()


@patch("questionary.select")
@patch("requests.request")
def test_retryable_request_retry_then_success(mock_request, mock_questionary):
    """Tests the retry mechanism."""
    mock_success = MagicMock()
    mock_success.raise_for_status.return_value = None

    # Fail first, then succeed
    mock_request.side_effect = [
        requests.RequestException("Connection failed"),
        mock_success,
    ]
    # User chooses to "Retry"
    mock_questionary.return_value.ask.return_value = "Retry"

    with patch("time.sleep"):  # Patch sleep to speed up the test
        response = retryable_request(method="get", url="http://example.com")

    assert response == mock_success
    assert mock_request.call_count == 2


@patch("questionary.select")
@patch("requests.request", side_effect=requests.RequestException("Connection failed"))
def test_retryable_request_skip(mock_request, mock_questionary):
    """Tests that SkipSignal is raised when the user chooses to skip."""
    mock_questionary.return_value.ask.return_value = "Skip"

    with pytest.raises(SkipSignal):
        retryable_request(method="get", url="http://example.com")


@patch("questionary.select")
@patch("requests.request", side_effect=requests.RequestException("Connection failed"))
def test_retryable_request_abort(mock_request, mock_questionary):
    """Tests that sys.exit is called when the user chooses to abort."""
    mock_questionary.return_value.ask.return_value = "Abort"

    with pytest.raises(SystemExit) as excinfo:
        retryable_request(method="get", url="http://example.com")
    assert excinfo.value.code == 1


@patch("builtins.print")
@patch("questionary.select")
@patch("requests.request")
def test_retryable_request_with_json_message(
    mock_request, mock_questionary, mock_print
):
    """Tests that details from a JSON response with a "message" key are printed."""
    mock_error_response = MagicMock()
    mock_error_response.json.return_value = {"message": "Invalid credentials provided."}
    http_error = requests.HTTPError("401 Client Error", response=mock_error_response)
    mock_request.side_effect = http_error
    mock_questionary.return_value.ask.return_value = "Abort"

    with pytest.raises(SystemExit):
        retryable_request(method="get", url="http://example.com")

    printed_output = mock_print.call_args_list[0].args[0]
    assert "401 Client Error" in printed_output
    assert "└── Details: Invalid credentials provided." in printed_output


@patch("builtins.print")
@patch("questionary.select")
@patch("requests.request")
def test_retryable_request_with_json_no_message(
    mock_request, mock_questionary, mock_print
):
    """Tests that if the JSON exists but has no "message" key, it fails gracefully."""
    mock_error_response = MagicMock()
    mock_error_response.json.return_value = {"error_code": 123, "info": "Some issue"}
    http_error = requests.HTTPError("400 Bad Request", response=mock_error_response)
    mock_request.side_effect = http_error
    mock_questionary.return_value.ask.return_value = "Abort"

    with pytest.raises(SystemExit):
        retryable_request(method="get", url="http://example.com")

    printed_output = mock_print.call_args_list[0].args[0]
    assert "400 Bad Request" in printed_output
    assert "└── Details:" not in printed_output


@patch("time.sleep")
@patch("builtins.print")
@patch("questionary.select")
@patch("requests.request")
def test_retryable_request_retries_then_aborts(
    mock_request, mock_questionary, mock_print, mock_sleep
):
    """Tests the retry mechanism with a 503 error and aborts."""
    http_error = requests.HTTPError("503 Service Unavailable")
    mock_request.side_effect = http_error
    mock_questionary.return_value.ask.side_effect = ["Retry", "Abort"]

    with pytest.raises(SystemExit):
        retryable_request(method="get", url="http://example.com")

    assert mock_request.call_count == 2
    assert mock_print.call_count == 3
    mock_sleep.assert_called_once_with(1)

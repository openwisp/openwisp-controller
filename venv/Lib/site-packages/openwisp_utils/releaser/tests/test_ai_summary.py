from unittest.mock import ANY, MagicMock, patch

import pytest
import requests
from openwisp_utils.releaser.release import get_ai_summary
from openwisp_utils.releaser.utils import SkipSignal

SAMPLE_CONTENT = "## [Unreleased]\n\n- feat: A new feature\n- fix: A bug fix"
AI_SUMMARY = "### Features\n\n- Added a cool new feature.\n\n### Bug Fixes\n\n- Fixed a critical bug."


@pytest.fixture
def mock_ai_response():
    """Provides a mock successful response from the OpenAI API."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": AI_SUMMARY}}]
    }
    return mock_response


@patch("openwisp_utils.releaser.release.questionary")
def test_get_ai_summary_user_declines(mock_questionary):
    """Tests that if the user declines the AI summary, the original content is returned."""
    mock_questionary.confirm.return_value.ask.return_value = False
    result = get_ai_summary(SAMPLE_CONTENT, "rst", "fake-token")
    assert result == SAMPLE_CONTENT
    mock_questionary.confirm.assert_called_once()


@patch("openwisp_utils.releaser.release.questionary")
@patch("builtins.print")
def test_get_ai_summary_no_token(mock_print, mock_questionary):
    """Tests that if the AI is requested but the token is missing, it skips and returns original content."""
    mock_questionary.confirm.return_value.ask.return_value = True
    result = get_ai_summary(SAMPLE_CONTENT, "rst", token=None)
    assert result == SAMPLE_CONTENT
    mock_print.assert_called_with(
        "⚠️ OPENAI_CHATGPT_TOKEN environment variable is not set. Skipping AI summary.",
        file=ANY,
    )


@patch("openwisp_utils.releaser.release.retryable_request")
@patch("openwisp_utils.releaser.release.questionary")
def test_get_ai_summary_success_accepted(
    mock_questionary, mock_retryable_request, mock_ai_response
):
    """Tests the successful flow where the AI generates a summary and the user accepts it."""
    mock_questionary.confirm.return_value.ask.return_value = True
    mock_questionary.select.return_value.ask.return_value = "Accept"
    mock_retryable_request.return_value = mock_ai_response

    result = get_ai_summary(SAMPLE_CONTENT, "rst", "fake-token")

    assert result == AI_SUMMARY
    mock_retryable_request.assert_called_once()


@patch("openwisp_utils.releaser.release.retryable_request")
@patch("openwisp_utils.releaser.release.questionary")
def test_get_ai_summary_retry_and_accept(
    mock_questionary, mock_retryable_request, mock_ai_response
):
    """Tests the flow where the user retries AI generation and then accepts."""
    mock_questionary.confirm.return_value.ask.return_value = True
    mock_questionary.select.return_value.ask.side_effect = ["Retry", "Accept"]
    mock_retryable_request.return_value = mock_ai_response

    result = get_ai_summary(SAMPLE_CONTENT, "rst", "fake-token")

    assert result == AI_SUMMARY
    assert mock_retryable_request.call_count == 2


@patch(
    "openwisp_utils.releaser.release.retryable_request",
    side_effect=requests.RequestException("API down"),
)
@patch("openwisp_utils.releaser.release.questionary")
def test_get_ai_summary_api_error(mock_questionary, mock_retryable_request):
    """Tests that if the API call fails, the original content is returned."""
    mock_questionary.confirm.return_value.ask.return_value = True
    result = get_ai_summary(SAMPLE_CONTENT, "rst", "fake-token")
    assert result == SAMPLE_CONTENT


@patch(
    "openwisp_utils.releaser.release.retryable_request",
    side_effect=SkipSignal("User skipped"),
)
@patch("openwisp_utils.releaser.release.questionary")
def test_get_ai_summary_skip_on_network_error(mock_questionary, mock_retryable_request):
    """Tests that if the user skips the network call, the original content is returned."""
    mock_questionary.confirm.return_value.ask.return_value = True
    result = get_ai_summary(SAMPLE_CONTENT, "rst", "fake-token")
    assert result == SAMPLE_CONTENT
    mock_retryable_request.assert_called_once()


@patch("openwisp_utils.releaser.release.retryable_request")
@patch("openwisp_utils.releaser.release.questionary")
def test_get_ai_summary_user_selects_original(
    mock_questionary, mock_retryable_request, mock_ai_response
):
    """Tests the flow where the user requests an AI summary but then chooses to use the original."""
    mock_questionary.confirm.return_value.ask.return_value = True
    mock_questionary.select.return_value.ask.return_value = (
        "Use Original (from git-cliff)"
    )
    mock_retryable_request.return_value = mock_ai_response
    result = get_ai_summary(SAMPLE_CONTENT, "rst", "fake-token")
    assert result == SAMPLE_CONTENT
    mock_retryable_request.assert_called_once()


@patch("openwisp_utils.releaser.release.retryable_request")
@patch("openwisp_utils.releaser.release.questionary")
def test_get_ai_summary_invalid_decision_fallback(
    mock_questionary, mock_retryable_request, mock_ai_response
):
    """Tests the `else` fallback if the user's decision is not recognized."""
    mock_questionary.confirm.return_value.ask.return_value = True
    mock_questionary.select.return_value.ask.return_value = "Invalid Option"
    mock_retryable_request.return_value = mock_ai_response
    result = get_ai_summary(SAMPLE_CONTENT, "rst", "fake-token")
    assert result == SAMPLE_CONTENT

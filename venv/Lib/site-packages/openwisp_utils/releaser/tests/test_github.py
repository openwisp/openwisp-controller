from unittest.mock import MagicMock, patch

import pytest
import requests
from openwisp_utils.releaser.github import GitHub


def mock_response(status_code=200, json_data=None, text=""):
    """Helper to create a mock requests.Response object for testing."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = text
    mock_resp.json.return_value = json_data if json_data is not None else {}

    def raise_for_status():
        if status_code >= 400:
            http_error = requests.HTTPError(response=mock_resp)
            http_error.response = mock_resp
            raise http_error

    mock_resp.raise_for_status = MagicMock(side_effect=raise_for_status)
    return mock_resp


@pytest.fixture
def github_client():
    return GitHub(token="fake-token", repo="owner/repo")


def test_github_init_failures():
    with pytest.raises(ValueError, match="GitHub token is required"):
        GitHub(token=None, repo="owner/repo")
    with pytest.raises(ValueError, match="repository name .* is required"):
        GitHub(token="fake-token", repo=None)


@patch("openwisp_utils.releaser.github.retryable_request")
def test_create_pr(mock_retryable_request, github_client):
    mock_retryable_request.return_value = mock_response(
        200, {"html_url": "http://example.com"}
    )
    url = github_client.create_pr("feature-branch", "main", "New Feature")
    assert url == "http://example.com"
    mock_retryable_request.assert_called_once()
    call_args = mock_retryable_request.call_args[1]
    assert call_args["url"].endswith("/pulls")
    assert call_args["json"]["title"] == "New Feature"


@patch("openwisp_utils.releaser.github.retryable_request")
def test_is_pr_merged(mock_retryable_request, github_client):
    mock_retryable_request.return_value = mock_response(200, {"merged": True})
    merged = github_client.is_pr_merged("http://example.com/pull/123")
    assert merged is True
    call_args = mock_retryable_request.call_args[1]
    assert call_args["url"].endswith("/pulls/123")


@patch("openwisp_utils.releaser.github.retryable_request")
def test_create_release(mock_retryable_request, github_client):
    mock_retryable_request.return_value = mock_response(
        200, {"html_url": "http://example.com"}
    )
    url = github_client.create_release("v1.0.0", "Version 1.0.0", "Release notes.")
    assert url == "http://example.com"
    call_args = mock_retryable_request.call_args[1]
    assert call_args["url"].endswith("/releases")
    assert call_args["json"]["tag_name"] == "v1.0.0"


@patch("openwisp_utils.releaser.github.utils_retryable_request")
def test_check_pr_creation_permission_success(mock_utils_request, github_client):
    """Tests the successful permission check flow where the probe fails as expected."""
    mock_utils_request.side_effect = [
        mock_response(200, {"default_branch": "main"}),
        mock_response(200, {"login": "testuser"}),
        mock_response(422, {"message": "Validation Failed"}),
    ]

    has_perm, reason = github_client.check_pr_creation_permission()

    assert has_perm is True
    assert "sufficient write permissions" in reason
    assert mock_utils_request.call_count == 3


@patch("openwisp_utils.releaser.github.utils_retryable_request")
def test_check_pr_creation_permission_failure(mock_utils_request, github_client):
    """Tests the permission check failing due to insufficient permissions (e.g., 401)."""
    mock_utils_request.side_effect = [
        mock_response(200, {"default_branch": "main"}),
        mock_response(401, {"message": "Bad credentials"}),
    ]

    has_perm, reason = github_client.check_pr_creation_permission()

    assert has_perm is False
    assert "Github permission failed with HTTP 401" in reason
    assert "Bad credentials" in reason
    assert mock_utils_request.call_count == 2


@patch(
    "openwisp_utils.releaser.github.utils_retryable_request",
    side_effect=requests.RequestException("Network Error"),
)
def test_check_pr_creation_permission_network_error(mock_utils_request, github_client):
    """Tests the permission check failing due to a network connectivity issue."""
    has_perm, reason = github_client.check_pr_creation_permission()

    assert has_perm is False
    assert "A network error occurred" in reason
    assert "Network Error" in reason

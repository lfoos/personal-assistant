"""Tests for DocsClient."""

from unittest.mock import MagicMock, patch

import pytest

from assistant.exceptions import IntegrationError
from assistant.integrations.docs import DocsClient


@pytest.fixture
def mock_auth_manager():
    manager = MagicMock()
    manager.get_credentials.return_value = MagicMock()
    return manager


@pytest.fixture
def docs_client(mock_auth_manager):
    with patch("assistant.integrations.docs.build"):
        return DocsClient(mock_auth_manager)


def test_create_doc_returns_id_and_url(docs_client):
    """create_doc() returns the doc ID and URL from the Drive API response."""
    docs_client._drive.files().create().execute.return_value = {
        "id": "abc123",
        "webViewLink": "https://docs.google.com/document/d/abc123/edit",
    }

    doc_id, doc_url = docs_client.create_doc("Personal Assistant — Daily Briefings")

    assert doc_id == "abc123"
    assert "abc123" in doc_url


def test_create_doc_raises_integration_error_on_failure(docs_client):
    """create_doc() raises IntegrationError when Drive API fails."""
    from googleapiclient.errors import HttpError

    resp = MagicMock()
    resp.status = 500
    docs_client._drive.files().create().execute.side_effect = HttpError(
        resp=resp, content=b"Server error"
    )

    with pytest.raises(IntegrationError, match="Failed to create Google Doc"):
        docs_client.create_doc("My Doc")


def test_append_section_inserts_at_correct_end_index(docs_client):
    """append_section() inserts text at endIndex - 1 of the last content element."""
    docs_client._docs.documents().get().execute.return_value = {
        "body": {"content": [{"endIndex": 1}, {"endIndex": 100}]}
    }
    docs_client._docs.documents().batchUpdate().execute.return_value = {}

    docs_client.append_section("doc123", "Hello world\n")

    batchUpdate_call = docs_client._docs.documents.return_value.batchUpdate
    call_body = batchUpdate_call.call_args.kwargs.get("body") or batchUpdate_call.call_args.args[1]
    request = call_body["requests"][0]
    assert request["insertText"]["location"]["index"] == 99
    assert request["insertText"]["text"] == "Hello world\n"


def test_append_section_raises_integration_error_on_404(docs_client):
    """append_section() raises IntegrationError with helpful message when doc is not found."""
    from googleapiclient.errors import HttpError

    resp = MagicMock()
    resp.status = 404
    docs_client._docs.documents().get().execute.side_effect = HttpError(
        resp=resp, content=b"Not found"
    )

    with pytest.raises(IntegrationError, match="Google Doc not found"):
        docs_client.append_section("deleted-doc-id", "content")


def test_append_section_raises_integration_error_on_other_api_failure(docs_client):
    """append_section() raises IntegrationError on non-404 API errors."""
    from googleapiclient.errors import HttpError

    resp = MagicMock()
    resp.status = 500
    docs_client._docs.documents().get().execute.side_effect = HttpError(
        resp=resp, content=b"Server error"
    )

    with pytest.raises(IntegrationError, match="Google Docs API error"):
        docs_client.append_section("doc123", "content")

"""Tests for GmailClient."""

from unittest.mock import MagicMock, patch

import pytest

from assistant.integrations.gmail import EmailMessage, GmailClient


@pytest.fixture
def mock_auth_manager():
    manager = MagicMock()
    manager.get_credentials.return_value = MagicMock()
    return manager


@pytest.fixture
def gmail_client(mock_auth_manager):
    with patch("assistant.integrations.gmail.build"):
        return GmailClient(mock_auth_manager)


def test_search_messages_returns_email_messages(gmail_client):
    """search_messages() returns a list of EmailMessage for each result."""
    gmail_client._service.users().messages().list().execute.return_value = {
        "messages": [{"id": "abc123"}]
    }
    gmail_client._service.users().messages().get().execute.return_value = {
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Posts you missed"},
                {"name": "From", "value": "LinkedIn <notifications@linkedin.com>"},
                {"name": "Date", "value": "Mon, 20 Apr 2026 10:00:00 +0000"},
            ],
            "mimeType": "text/plain",
            "body": {"data": ""},
        },
        "snippet": "Top posts from your network",
    }

    results = gmail_client.search_messages(query="from:linkedin.com", max_results=5)

    assert len(results) == 1
    assert isinstance(results[0], EmailMessage)
    assert results[0].subject == "Posts you missed"


def test_search_messages_returns_empty_list_when_no_results(gmail_client):
    """search_messages() returns [] when the query matches nothing."""
    gmail_client._service.users().messages().list().execute.return_value = {}

    results = gmail_client.search_messages(query="from:nobody.example.com", max_results=5)

    assert results == []


def test_search_messages_raises_integration_error_on_api_failure(gmail_client):
    """search_messages() raises IntegrationError when the Gmail API fails."""
    from googleapiclient.errors import HttpError
    from unittest.mock import MagicMock
    from assistant.exceptions import IntegrationError

    resp = MagicMock()
    resp.status = 500
    gmail_client._service.users().messages().list().execute.side_effect = HttpError(
        resp=resp, content=b"Server error"
    )

    with pytest.raises(IntegrationError):
        gmail_client.search_messages(query="from:linkedin.com", max_results=5)

"""Tests for LinkedInDigestClient."""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from assistant.integrations.gmail import EmailMessage
from assistant.integrations.linkedin import LinkedInDigestClient


@pytest.fixture
def mock_gmail_client():
    return MagicMock()


@pytest.fixture
def client(mock_gmail_client):
    return LinkedInDigestClient(mock_gmail_client)


def _make_email(subject="LinkedIn digest", sender="LinkedIn <noreply@linkedin.com>"):
    return EmailMessage(
        subject=subject,
        sender=sender,
        date="Mon, 20 Apr 2026 10:00:00 +0000",
        snippet="Top posts from your network",
        body="Post 1: AI is changing engineering...\nPost 2: Leadership tips...",
    )


def test_get_digest_emails_passes_correct_query(client, mock_gmail_client):
    """get_digest_emails() calls search_messages with a linkedin.com query."""
    mock_gmail_client.search_messages.return_value = []

    client.get_digest_emails(days=14)

    call_args = mock_gmail_client.search_messages.call_args
    query = call_args.kwargs.get("query") or call_args.args[0]
    assert "linkedin.com" in query


def test_get_digest_emails_includes_date_filter(client, mock_gmail_client):
    """get_digest_emails() includes an 'after:' date filter in the query."""
    mock_gmail_client.search_messages.return_value = []

    client.get_digest_emails(days=7)

    call_args = mock_gmail_client.search_messages.call_args
    query = call_args.kwargs.get("query") or call_args.args[0]
    expected_date = (date.today() - timedelta(days=7)).strftime("%Y/%m/%d")
    assert expected_date in query


def test_get_digest_emails_returns_email_messages(client, mock_gmail_client):
    """get_digest_emails() returns the list from search_messages."""
    emails = [_make_email(), _make_email(subject="Posts in your network")]
    mock_gmail_client.search_messages.return_value = emails

    result = client.get_digest_emails(days=14)

    assert result == emails


def test_get_digest_emails_returns_empty_when_none_found(client, mock_gmail_client):
    """get_digest_emails() returns [] when no LinkedIn emails exist."""
    mock_gmail_client.search_messages.return_value = []

    result = client.get_digest_emails(days=14)

    assert result == []

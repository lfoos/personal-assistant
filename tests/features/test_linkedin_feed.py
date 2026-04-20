"""Tests for LinkedInFeedFeature."""

from unittest.mock import MagicMock

import pytest

from assistant.integrations.gmail import EmailMessage
from assistant.features.linkedin_feed import LinkedInFeedFeature


@pytest.fixture
def mock_linkedin_client():
    return MagicMock()


@pytest.fixture
def mock_claude_client():
    return MagicMock()


@pytest.fixture
def feature(mock_linkedin_client, mock_claude_client):
    return LinkedInFeedFeature(mock_linkedin_client, mock_claude_client)


def _make_email(body="Post 1: AI trends...\nPost 2: Leadership tips..."):
    return EmailMessage(
        subject="Posts you missed on LinkedIn",
        sender="LinkedIn <noreply@linkedin.com>",
        date="Mon, 20 Apr 2026 10:00:00 +0000",
        snippet="Top posts from your network",
        body=body,
    )


def test_run_yields_no_emails_message_when_empty(feature, mock_linkedin_client):
    """run() yields a helpful message when no digest emails are found."""
    mock_linkedin_client.get_digest_emails.return_value = []

    chunks = list(feature.run(days=14))

    assert len(chunks) == 1
    assert "LinkedIn" in chunks[0]
    assert "notification" in chunks[0].lower() or "digest" in chunks[0].lower()


def test_run_streams_claude_response_when_emails_present(
    feature, mock_linkedin_client, mock_claude_client
):
    """run() streams Claude's response when digest emails exist."""
    mock_linkedin_client.get_digest_emails.return_value = [_make_email()]
    mock_claude_client.stream_response.return_value = iter(["Trending: ", "AI agents"])

    chunks = list(feature.run(days=14))

    assert chunks == ["Trending: ", "AI agents"]
    mock_claude_client.stream_response.assert_called_once()


def test_run_passes_email_content_to_claude(
    feature, mock_linkedin_client, mock_claude_client
):
    """run() includes email body content in the Claude prompt."""
    mock_linkedin_client.get_digest_emails.return_value = [
        _make_email(body="Everyone is talking about vibe coding")
    ]
    mock_claude_client.stream_response.return_value = iter([])

    list(feature.run(days=14))

    _, user_message = mock_claude_client.stream_response.call_args.args
    assert "vibe coding" in user_message


def test_run_passes_days_to_client(feature, mock_linkedin_client, mock_claude_client):
    """run() passes the days argument through to the LinkedIn client."""
    mock_linkedin_client.get_digest_emails.return_value = []

    list(feature.run(days=7))

    mock_linkedin_client.get_digest_emails.assert_called_once_with(days=7)

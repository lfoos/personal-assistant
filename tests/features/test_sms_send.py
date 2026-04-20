"""Tests for SmsSendFeature."""

from unittest.mock import MagicMock

import pytest

from assistant.exceptions import IntegrationError
from assistant.features.sms_send import SmsSendFeature


@pytest.fixture
def mock_claude():
    return MagicMock()


@pytest.fixture
def mock_sms():
    return MagicMock()


@pytest.fixture
def feature(mock_claude, mock_sms):
    return SmsSendFeature(mock_claude, mock_sms)


def test_claude_summary_is_sent_as_sms_body(feature, mock_claude, mock_sms):
    """run() passes the Claude-generated summary as the SMS body."""
    mock_claude.stream_response.return_value = iter(["Fix prod bug. Review PR #42."])
    list(feature.run("Long email content here...", "+15551234567"))
    mock_sms.send.assert_called_once_with("+15551234567", "Fix prod bug. Review PR #42.")


def test_recipient_number_passed_through_correctly(feature, mock_claude, mock_sms):
    """run() passes the `to` number to sms_client.send unchanged."""
    mock_claude.stream_response.return_value = iter(["Summary"])
    list(feature.run("content", "+19998887777"))
    mock_sms.send.assert_called_once_with("+19998887777", "Summary")


def test_confirmation_message_is_yielded(feature, mock_claude, mock_sms):
    """run() yields a confirmation string after sending."""
    mock_claude.stream_response.return_value = iter(["Summary"])
    result = list(feature.run("content", "+15551234567"))
    assert result == ["✅ SMS sent to +15551234567"]


def test_integration_error_from_sms_propagates(feature, mock_claude, mock_sms):
    """run() lets IntegrationError from sms_client.send propagate."""
    mock_claude.stream_response.return_value = iter(["Summary"])
    mock_sms.send.side_effect = IntegrationError("SNS quota exceeded")
    with pytest.raises(IntegrationError):
        list(feature.run("content", "+15551234567"))


def test_llm_error_from_claude_propagates(feature, mock_claude):
    """run() lets LLMError from claude.stream_response propagate."""
    from assistant.exceptions import LLMError
    mock_claude.stream_response.side_effect = LLMError("API failure")
    with pytest.raises(LLMError):
        list(feature.run("content", "+15551234567"))


def test_empty_claude_summary_raises_llm_error(feature, mock_claude):
    """run() raises LLMError if Claude returns an empty or whitespace-only summary."""
    from assistant.exceptions import LLMError
    mock_claude.stream_response.return_value = iter(["   "])
    with pytest.raises(LLMError):
        list(feature.run("content", "+15551234567"))

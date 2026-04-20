"""Tests for SmsClient."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from assistant.exceptions import IntegrationError
from assistant.integrations.sms import SmsClient


@pytest.fixture
def sms_client_and_mock():
    with patch("assistant.integrations.sms.boto3") as mock_boto:
        mock_sns = MagicMock()
        mock_boto.client.return_value = mock_sns
        yield SmsClient(), mock_sns


def test_send_calls_sns_publish_with_correct_params(sms_client_and_mock):
    """send() calls sns.publish with PhoneNumber and Message."""
    client, mock_sns = sms_client_and_mock
    client.send("+15551234567", "Hello world")
    mock_sns.publish.assert_called_once_with(
        PhoneNumber="+15551234567",
        Message="Hello world",
    )


def test_send_raises_integration_error_on_client_error(sms_client_and_mock):
    """send() raises IntegrationError when SNS returns a ClientError."""
    client, mock_sns = sms_client_and_mock
    mock_sns.publish.side_effect = ClientError(
        {"Error": {"Code": "InvalidParameter", "Message": "Invalid phone number"}},
        "Publish",
    )
    with pytest.raises(IntegrationError) as exc_info:
        client.send("+15551234567", "Hello world")
    assert isinstance(exc_info.value.__cause__, ClientError)

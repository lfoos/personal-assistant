"""AWS SNS SMS integration."""

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from assistant.exceptions import IntegrationError


class SmsClient:
    """Sends SMS messages via AWS SNS direct publish."""

    def __init__(self) -> None:
        try:
            self._sns = boto3.client("sns")
        except (ClientError, BotoCoreError) as e:
            raise IntegrationError(f"Failed to initialize SNS client: {e}") from e

    def send(self, to: str, body: str) -> None:
        """Send an SMS to the given E.164 phone number.

        Args:
            to: Recipient phone number in E.164 format (e.g. "+15551234567").
            body: Message text to send.

        Raises:
            IntegrationError: On SNS API failure.
        """
        try:
            self._sns.publish(PhoneNumber=to, Message=body)
        except (ClientError, BotoCoreError) as e:
            raise IntegrationError(f"SMS send failed: {e}") from e

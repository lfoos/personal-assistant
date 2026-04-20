"""SMS send feature — summarizes content with Claude and sends via AWS SNS."""

from collections.abc import Iterator

from assistant.exceptions import LLMError
from assistant.integrations.sms import SmsClient
from assistant.llm.claude import ClaudeClient

_SYSTEM_PROMPT = (
    "You are a personal assistant summarizer. The user will provide output from an AI assistant. "
    "Extract the 3-5 most important action items or insights. "
    "Write in plain text only — no markdown, no bullet symbols, no headers. "
    "Keep the total response under 1200 characters. Be direct and specific."
)

_MAX_SMS_CHARS = 1200


class SmsSendFeature:
    """Summarizes assistant output with Claude and delivers it as an SMS."""

    def __init__(self, claude_client: ClaudeClient, sms_client: SmsClient) -> None:
        self._claude = claude_client
        self._sms = sms_client

    def run(self, content: str, to: str) -> Iterator[str]:
        """Summarize content with Claude and send it via SMS.

        Args:
            content: The full text output from another assistant feature.
            to: Recipient phone number in E.164 format.

        Yields:
            A single confirmation string after the SMS is sent.

        Raises:
            LLMError: If the Claude summarization call fails or returns empty output.
            IntegrationError: If the SNS send fails.
        """
        summary = "".join(self._claude.stream_response(_SYSTEM_PROMPT, content))
        if not summary.strip():
            raise LLMError("Claude returned an empty summary")
        self._sms.send(to, summary[:_MAX_SMS_CHARS])
        yield f"✅ SMS sent to {to}"

"""Email action items feature."""

from collections.abc import Iterator
from typing import ClassVar

from assistant.integrations.gmail import EmailMessage, GmailClient
from assistant.llm.claude import ClaudeClient

_SYSTEM_PROMPT = """You are a personal productivity assistant. Review the user's recent
emails and identify the 2-3 most important action items they need to address. Focus on:
- Emails requiring a response or decision
- Time-sensitive requests or deadlines
- Important tasks assigned to them
- Anything that could have negative consequences if ignored

Be concise and specific. For each action item include: what needs to be done, who it
involves (if relevant), and any deadline or urgency level.

Ignore newsletters, promotional emails, and automated notifications unless they contain
something genuinely important."""


class EmailActionItemsFeature:
    """Fetches recent emails and streams prioritized action items."""

    _DEFAULT_MAX_EMAILS: ClassVar[int] = 20

    def __init__(self, gmail_client: GmailClient, claude_client: ClaudeClient) -> None:
        self._gmail = gmail_client
        self._claude = claude_client

    def run(self, max_emails: int = _DEFAULT_MAX_EMAILS) -> Iterator[str]:
        """Fetch emails and stream 2-3 action items as text chunks."""
        emails = self._gmail.get_recent_messages(max_results=max_emails)
        user_message = self._build_prompt(emails)
        yield from self._claude.stream_response(_SYSTEM_PROMPT, user_message)

    def _build_prompt(self, emails: list[EmailMessage]) -> str:
        blocks = []
        for i, email in enumerate(emails, 1):
            blocks.append(
                f"--- Email {i} ---\n"
                f"From: {email.sender}\n"
                f"Date: {email.date}\n"
                f"Subject: {email.subject}\n"
                f"Body:\n{email.body or email.snippet}"
            )
        body = "\n\n".join(blocks)
        return (
            f"Here are my {len(emails)} most recent emails. "
            f"Please identify the 2-3 most important action items I need to address.\n\n"
            f"{body}"
        )

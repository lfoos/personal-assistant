"""LinkedIn network feed summary feature."""

from collections.abc import Iterator

from assistant.integrations.gmail import EmailMessage
from assistant.integrations.linkedin import LinkedInDigestClient
from assistant.llm.claude import ClaudeClient

_NO_EMAILS_MESSAGE = (
    "No LinkedIn digest emails found. To enable them, go to LinkedIn → "
    "Settings & Privacy → Notifications → Email → turn on 'Digest emails' "
    "or 'Posts in your network'."
)

_SYSTEM_PROMPT = """You are a personal productivity assistant summarizing a professional's
LinkedIn network activity from their digest emails.

About the user: They work in software engineering leadership (previously at Spotify,
currently at a company called Keebo). They manage engineering teams and care about
trends in software engineering, leadership, AI, and the tech industry broadly.

Produce exactly two sections:

## Trending Themes
2-3 bullet points on what the network is discussing this week. Be specific —
name the actual topics, not generic descriptions like "people are talking about tech".

## Worth Your Attention
2-3 specific posts, threads, or topics the user should engage with or be aware of,
each with one sentence explaining why it's relevant to them professionally.

Filter out noise: job announcements, generic motivational content, and self-promotion
unless genuinely notable. Surface signal."""


class LinkedInFeedFeature:
    """Reads LinkedIn digest emails and streams a network activity briefing."""

    def __init__(
        self, linkedin_client: LinkedInDigestClient, claude_client: ClaudeClient
    ) -> None:
        self._linkedin = linkedin_client
        self._claude = claude_client

    def run(self, days: int = 14) -> Iterator[str]:
        """Fetch digest emails and stream a LinkedIn network summary.

        Yields a single explanatory string if no digest emails are found.
        Otherwise streams Claude's response as text chunks.
        """
        emails = self._linkedin.get_digest_emails(days=days)

        if not emails:
            yield _NO_EMAILS_MESSAGE
            return

        user_message = self._build_prompt(emails)
        yield from self._claude.stream_response(_SYSTEM_PROMPT, user_message)

    def _build_prompt(self, emails: list[EmailMessage]) -> str:
        blocks = []
        for i, email in enumerate(emails, 1):
            blocks.append(
                f"--- Digest {i} ---\n"
                f"Date: {email.date}\n"
                f"Subject: {email.subject}\n"
                f"Content:\n{email.body or email.snippet}"
            )
        content = "\n\n".join(blocks)
        return (
            f"Here are {len(emails)} LinkedIn digest email(s) from my network. "
            f"Please summarize what my network is talking about and what I should pay attention to.\n\n"
            f"{content}"
        )

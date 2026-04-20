"""Calendar event preparation feature."""

from collections.abc import Iterator

from assistant.integrations.calendar import CalendarClient, CalendarEvent
from assistant.llm.claude import ClaudeClient

_SYSTEM_PROMPT = """You are a personal productivity assistant helping the user prepare
for an upcoming calendar event. Based on the event details provided, generate:

1. **Context Summary** — A brief paragraph explaining what this event likely involves
   and why it matters, inferred from the title, description, attendees, and timing.

2. **Preparation Checklist** — 3-5 concrete steps the user should take before the event
   (e.g., review documents, prepare talking points, confirm logistics).

3. **Open Questions** — 2-3 things the user should clarify or resolve before the event
   to ensure it goes smoothly.

Be specific and actionable. Draw on any context clues in the event details.

About the user: They work in software engineering leadership (previously at Spotify,
currently at a company called Keebo). They manage engineering teams and are involved
in code reviews, technical decisions, and cross-functional collaboration."""


class CalendarPrepFeature:
    """Fetches a calendar event and streams preparation notes."""

    def __init__(
        self, calendar_client: CalendarClient, claude_client: ClaudeClient
    ) -> None:
        self._calendar = calendar_client
        self._claude = claude_client

    def list_upcoming(self, max_results: int = 10) -> list[CalendarEvent]:
        """Return upcoming calendar events for display."""
        return self._calendar.get_upcoming_events(max_results=max_results)

    def run(self, event_id: str) -> Iterator[str]:
        """Fetch a calendar event and stream preparation notes as text chunks."""
        event = self._calendar.get_event_by_id(event_id)
        user_message = self._build_prompt(event)
        yield from self._claude.stream_response(_SYSTEM_PROMPT, user_message)

    def _build_prompt(self, event: CalendarEvent) -> str:
        attendee_list = ", ".join(event.attendees) if event.attendees else "just you"
        start_fmt = event.start.strftime("%A, %B %-d at %-I:%M %p")

        lines = [
            f"Please help me prepare for the following event:\n",
            f"**Title:** {event.summary}",
            f"**When:** {start_fmt} ({event.duration_minutes} minutes)",
        ]
        if event.location:
            lines.append(f"**Location:** {event.location}")
        lines.append(f"**Attendees:** {attendee_list}")
        if event.description:
            lines.append(f"**Description:**\n{event.description}")

        return "\n".join(lines)

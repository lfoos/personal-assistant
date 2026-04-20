"""Daily briefing feature — orchestrates email and calendar prep, writes to Google Docs."""

from datetime import date as Date

from assistant.features.calendar_prep import CalendarPrepFeature
from assistant.features.email_actions import EmailActionItemsFeature
from assistant.integrations.calendar import CalendarClient, CalendarEvent
from assistant.integrations.docs import DocsClient
from assistant.integrations.gmail import GmailClient
from assistant.llm.claude import ClaudeClient

_DOC_TITLE = "Personal Assistant — Daily Briefings"
_SEPARATOR = "━" * 60
_THIN_SEP_EMAIL = "─" * 18
_THIN_SEP_CAL = "─" * 13


class DailyBriefingFeature:
    """Collects email action items and per-event calendar prep for a given day,
    then appends a dated section to a Google Doc."""

    def __init__(
        self,
        gmail_client: GmailClient,
        calendar_client: CalendarClient,
        claude_client: ClaudeClient,
        docs_client: DocsClient,
    ) -> None:
        self._gmail = gmail_client
        self._calendar = calendar_client
        self._claude = claude_client
        self._docs = docs_client

    def run(self, target_date: Date, doc_id: str | None) -> tuple[str, str]:
        """Generate a daily briefing and append it to a Google Doc.

        On first run (doc_id=None), creates a new doc and returns its ID so the
        caller can persist it. On subsequent runs, appends to the existing doc.

        Returns:
            (doc_id, doc_url)

        Raises:
            IntegrationError: If email fetching or doc operations fail.
        """
        # Email errors propagate intentionally — if we can't get emails, abort
        # before writing an incomplete briefing to the doc.
        email_output = "".join(
            EmailActionItemsFeature(self._gmail, self._claude).run()
        )

        events = self._calendar.get_events_for_date(target_date)
        event_preps: list[tuple[CalendarEvent, str]] = []
        for event in events:
            try:
                prep = "".join(
                    CalendarPrepFeature(self._calendar, self._claude).run(event.event_id)
                )
            except Exception as exc:  # noqa: BLE001
                prep = f"[Error generating prep for this event: {exc}]"
            event_preps.append((event, prep))

        content = self._build_section(target_date, email_output, event_preps)

        if doc_id is None:
            doc_id, doc_url = self._docs.create_doc(_DOC_TITLE)
        else:
            doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

        self._docs.append_section(doc_id, content)
        return doc_id, doc_url

    def _build_section(
        self,
        target_date: Date,
        email_output: str,
        event_preps: list[tuple[CalendarEvent, str]],
    ) -> str:
        date_str = target_date.strftime("%A, %B %-d, %Y")
        parts = [
            f"\n{_SEPARATOR}",
            f"Daily Briefing — {date_str}",
            f"{_SEPARATOR}\n",
            "EMAIL ACTION ITEMS",
            _THIN_SEP_EMAIL,
            email_output,
            "\n\nCALENDAR PREP",
            _THIN_SEP_CAL,
        ]
        if not event_preps:
            parts.append("No events scheduled for this day.")
        else:
            for event, prep in event_preps:
                start_fmt = event.start.strftime("%-I:%M %p")
                parts.append(
                    f"\nEvent: {event.summary} ({start_fmt}, {event.duration_minutes} min)"
                )
                parts.append(prep)
        return "\n".join(parts) + "\n"

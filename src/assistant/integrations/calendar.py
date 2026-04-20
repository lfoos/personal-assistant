"""Google Calendar API integration."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from assistant.exceptions import EventNotFoundError, IntegrationError
from assistant.integrations.base import GoogleAuthManager


@dataclass
class CalendarEvent:
    event_id: str
    summary: str
    description: str
    start: datetime
    end: datetime
    attendees: list[str] = field(default_factory=list)
    location: str = ""
    html_link: str = ""

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() / 60)


class CalendarClient:
    """Fetches events from the authenticated user's primary Google Calendar."""

    def __init__(self, auth_manager: GoogleAuthManager) -> None:
        creds = auth_manager.get_credentials()
        self._service = build("calendar", "v3", credentials=creds)

    def get_upcoming_events(
        self,
        max_results: int = 10,
        time_min: datetime | None = None,
    ) -> list[CalendarEvent]:
        """Return upcoming events ordered by start time.

        Raises:
            IntegrationError: On Calendar API failure.
        """
        if time_min is None:
            time_min = datetime.now(timezone.utc)

        try:
            results = (
                self._service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min.isoformat(),
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            return [self._parse_event(e) for e in results.get("items", [])]
        except HttpError as e:
            raise IntegrationError(f"Calendar API error: {e}") from e

    def get_event_by_id(self, event_id: str) -> CalendarEvent:
        """Fetch a single event by ID.

        Raises:
            EventNotFoundError: If the event does not exist.
            IntegrationError: On other API failures.
        """
        try:
            event = (
                self._service.events()
                .get(calendarId="primary", eventId=event_id)
                .execute()
            )
            return self._parse_event(event)
        except HttpError as e:
            if e.resp.status == 404:
                raise EventNotFoundError(f"Event '{event_id}' not found.") from e
            raise IntegrationError(f"Calendar API error: {e}") from e

    def get_events_for_date(self, target_date: date) -> list[CalendarEvent]:
        """Return all events on the given date, ordered by start time.

        Uses midnight UTC as the start boundary and next-day midnight as the exclusive end boundary.

        Raises:
            IntegrationError: On Calendar API failure.
        """
        time_min = datetime(
            target_date.year, target_date.month, target_date.day, 0, 0, 0,
            tzinfo=timezone.utc,
        )
        time_max = datetime(
            target_date.year, target_date.month, target_date.day, 0, 0, 0,
            tzinfo=timezone.utc,
        ) + timedelta(days=1)
        try:
            results = (
                self._service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    maxResults=50,  # sufficient for a personal calendar; no pagination needed
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            return [self._parse_event(e) for e in results.get("items", [])]
        except HttpError as e:
            raise IntegrationError(f"Calendar API error: {e}") from e

    def _parse_event(self, raw: dict) -> CalendarEvent:
        start = self._parse_dt(raw.get("start", {}))
        end = self._parse_dt(raw.get("end", {}))
        attendees = [
            a.get("displayName") or a.get("email", "")
            for a in raw.get("attendees", [])
        ]
        return CalendarEvent(
            event_id=raw["id"],
            summary=raw.get("summary", "(no title)"),
            description=raw.get("description", ""),
            start=start,
            end=end,
            attendees=attendees,
            location=raw.get("location", ""),
            html_link=raw.get("htmlLink", ""),
        )

    def _parse_dt(self, dt_dict: dict) -> datetime:
        raw = dt_dict.get("dateTime") or dt_dict.get("date", "")
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)

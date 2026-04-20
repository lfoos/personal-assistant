"""Pure formatting functions — no I/O, no side effects."""

from assistant.integrations.calendar import CalendarEvent


def format_event_list(events: list[CalendarEvent]) -> str:
    """Format a numbered list of upcoming events for terminal display."""
    if not events:
        return "No upcoming events found."

    lines = []
    for i, event in enumerate(events, 1):
        day = event.start.strftime("%a %b %-d")
        time = event.start.strftime("%-I:%M %p")
        duration = f"{event.duration_minutes}m"
        attendee_count = len(event.attendees)
        attendees = f" · {attendee_count} attendee{'s' if attendee_count != 1 else ''}" if attendee_count else ""
        lines.append(
            f"  {i:>2}. [{day}, {time}] {event.summary} ({duration}){attendees}\n"
            f"      ID: {event.event_id}"
        )
    return "\n".join(lines)


def format_event_detail(event: CalendarEvent) -> str:
    """Format full event details shown before Claude's preparation notes."""
    start = event.start.strftime("%A, %B %-d at %-I:%M %p")
    lines = [
        f"Event:    {event.summary}",
        f"When:     {start} ({event.duration_minutes} min)",
    ]
    if event.location:
        lines.append(f"Location: {event.location}")
    if event.attendees:
        lines.append(f"Attendees: {', '.join(event.attendees)}")
    return "\n".join(lines)

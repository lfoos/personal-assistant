"""Tests for CalendarClient.get_events_for_date."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from assistant.integrations.calendar import CalendarClient, CalendarEvent


@pytest.fixture
def mock_auth_manager():
    manager = MagicMock()
    manager.get_credentials.return_value = MagicMock()
    return manager


@pytest.fixture
def calendar_client(mock_auth_manager):
    with patch("assistant.integrations.calendar.build"):
        return CalendarClient(mock_auth_manager)


def _raw_event(event_id="evt1", summary="Standup"):
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": "2026-04-21T09:00:00+00:00"},
        "end": {"dateTime": "2026-04-21T09:30:00+00:00"},
    }


def test_get_events_for_date_queries_correct_time_range(calendar_client):
    """get_events_for_date() calls the API with timeMin at midnight and timeMax at next-day midnight."""
    calendar_client._service.events().list().execute.return_value = {"items": []}

    calendar_client.get_events_for_date(date(2026, 4, 21))

    list_call = calendar_client._service.events.return_value.list
    kwargs = list_call.call_args.kwargs
    assert kwargs["timeMin"] == "2026-04-21T00:00:00+00:00"
    assert kwargs["timeMax"] == "2026-04-22T00:00:00+00:00"


def test_get_events_for_date_returns_calendar_events(calendar_client):
    """get_events_for_date() returns a list of CalendarEvent."""
    calendar_client._service.events().list().execute.return_value = {
        "items": [_raw_event("evt1", "Standup"), _raw_event("evt2", "All Hands")]
    }

    events = calendar_client.get_events_for_date(date(2026, 4, 21))

    assert len(events) == 2
    assert all(isinstance(e, CalendarEvent) for e in events)
    assert events[0].summary == "Standup"
    assert events[1].summary == "All Hands"


def test_get_events_for_date_returns_empty_list_when_no_events(calendar_client):
    """get_events_for_date() returns [] when no events exist on that day."""
    calendar_client._service.events().list().execute.return_value = {"items": []}

    events = calendar_client.get_events_for_date(date(2026, 4, 21))

    assert events == []

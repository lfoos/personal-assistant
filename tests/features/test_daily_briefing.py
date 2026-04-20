"""Tests for DailyBriefingFeature."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from assistant.features.daily_briefing import DailyBriefingFeature
from assistant.integrations.calendar import CalendarEvent


def _make_event(event_id="evt1", summary="Standup"):
    return CalendarEvent(
        event_id=event_id,
        summary=summary,
        description="",
        start=datetime(2026, 4, 21, 9, 0, tzinfo=timezone.utc),
        end=datetime(2026, 4, 21, 9, 30, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_gmail():
    return MagicMock()


@pytest.fixture
def mock_calendar():
    return MagicMock()


@pytest.fixture
def mock_claude():
    return MagicMock()


@pytest.fixture
def mock_docs():
    return MagicMock()


@pytest.fixture
def feature(mock_gmail, mock_calendar, mock_claude, mock_docs):
    return DailyBriefingFeature(mock_gmail, mock_calendar, mock_claude, mock_docs)


def test_first_run_creates_doc_and_returns_id(feature, mock_docs):
    """run() with doc_id=None calls create_doc and returns the new doc_id."""
    mock_docs.create_doc.return_value = (
        "doc123",
        "https://docs.google.com/document/d/doc123/edit",
    )
    feature._calendar.get_events_for_date.return_value = []

    with patch("assistant.features.daily_briefing.EmailActionItemsFeature") as MockEmail, \
         patch("assistant.features.daily_briefing.CalendarPrepFeature"):
        MockEmail.return_value.run.return_value = iter([])
        doc_id, _ = feature.run(date(2026, 4, 21), None)

    mock_docs.create_doc.assert_called_once()
    assert doc_id == "doc123"


def test_subsequent_run_skips_create_doc(feature, mock_docs):
    """run() with a doc_id does not call create_doc."""
    feature._calendar.get_events_for_date.return_value = []

    with patch("assistant.features.daily_briefing.EmailActionItemsFeature") as MockEmail, \
         patch("assistant.features.daily_briefing.CalendarPrepFeature"):
        MockEmail.return_value.run.return_value = iter([])
        feature.run(date(2026, 4, 21), "existing-doc-id")

    mock_docs.create_doc.assert_not_called()
    mock_docs.append_section.assert_called_once()


def test_email_output_appears_in_section_content(feature, mock_docs):
    """run() includes email action items text in the appended section."""
    mock_docs.create_doc.return_value = (
        "doc123",
        "https://docs.google.com/document/d/doc123/edit",
    )
    feature._calendar.get_events_for_date.return_value = []

    with patch("assistant.features.daily_briefing.EmailActionItemsFeature") as MockEmail, \
         patch("assistant.features.daily_briefing.CalendarPrepFeature"):
        MockEmail.return_value.run.return_value = iter(["Fix the prod bug ASAP"])
        feature.run(date(2026, 4, 21), None)

    content = mock_docs.append_section.call_args.args[1]
    assert "Fix the prod bug ASAP" in content


def test_event_prep_output_appears_in_section_content(feature, mock_docs):
    """run() includes each event's prep text and event name in the section."""
    mock_docs.create_doc.return_value = (
        "doc123",
        "https://docs.google.com/document/d/doc123/edit",
    )
    feature._calendar.get_events_for_date.return_value = [_make_event()]

    with patch("assistant.features.daily_briefing.EmailActionItemsFeature") as MockEmail, \
         patch("assistant.features.daily_briefing.CalendarPrepFeature") as MockCalendar:
        MockEmail.return_value.run.return_value = iter([])
        MockCalendar.return_value.run.return_value = iter(["Review the agenda"])
        feature.run(date(2026, 4, 21), None)

    content = mock_docs.append_section.call_args.args[1]
    assert "Standup" in content
    assert "Review the agenda" in content


def test_no_events_writes_placeholder(feature, mock_docs):
    """run() writes 'No events scheduled' when get_events_for_date returns []."""
    mock_docs.create_doc.return_value = (
        "doc123",
        "https://docs.google.com/document/d/doc123/edit",
    )
    feature._calendar.get_events_for_date.return_value = []

    with patch("assistant.features.daily_briefing.EmailActionItemsFeature") as MockEmail, \
         patch("assistant.features.daily_briefing.CalendarPrepFeature"):
        MockEmail.return_value.run.return_value = iter([])
        feature.run(date(2026, 4, 21), None)

    content = mock_docs.append_section.call_args.args[1]
    assert "No events scheduled" in content


def test_per_event_error_inserts_note_and_continues(feature, mock_docs):
    """run() inserts an error note for a failing event and continues with the rest."""
    mock_docs.create_doc.return_value = (
        "doc123",
        "https://docs.google.com/document/d/doc123/edit",
    )
    feature._calendar.get_events_for_date.return_value = [
        _make_event("evt1", "Standup"),
        _make_event("evt2", "All Hands"),
    ]

    with patch("assistant.features.daily_briefing.EmailActionItemsFeature") as MockEmail, \
         patch("assistant.features.daily_briefing.CalendarPrepFeature") as MockCalendar:
        MockEmail.return_value.run.return_value = iter([])
        MockCalendar.return_value.run.side_effect = [
            Exception("Claude timeout"),
            iter(["Prepare slides for All Hands"]),
        ]
        feature.run(date(2026, 4, 21), None)

    content = mock_docs.append_section.call_args.args[1]
    assert "Error generating prep" in content
    assert "Prepare slides for All Hands" in content

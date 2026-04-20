# Daily Briefing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `assistant daily` command that collects email action items and calendar prep notes for all events on a given day, then appends a dated section to a persistent Google Doc (creating it on first run).

**Architecture:** A new `DocsClient` integration wraps the Google Docs + Drive APIs and handles document creation and text appending. `DailyBriefingFeature` orchestrates the run by composing `EmailActionItemsFeature` and `CalendarPrepFeature`, building a formatted section, and delegating to `DocsClient`. The doc ID is persisted in `.env` as `DAILY_BRIEFING_DOC_ID`.

**Tech Stack:** `google-api-python-client` (already installed) — Google Docs API v1, Google Drive API v3. New OAuth scopes: `documents`, `drive.file`.

---

## File Map

| File | Action |
|------|--------|
| `src/assistant/integrations/base.py` | Modify — add two OAuth scopes |
| `src/assistant/integrations/calendar.py` | Modify — add `get_events_for_date()` |
| `src/assistant/integrations/docs.py` | Create — `DocsClient` |
| `src/assistant/features/daily_briefing.py` | Create — `DailyBriefingFeature` |
| `src/assistant/cli/main.py` | Modify — add `daily` subcommand |
| `tests/integrations/test_calendar.py` | Create |
| `tests/integrations/test_docs.py` | Create |
| `tests/features/test_daily_briefing.py` | Create |

---

## Task 1: Create Feature Branch

**Files:** none

- [ ] **Step 1: Create and switch to feature branch**

```bash
cd /Users/lfoos/projects/personal-assistant
git checkout -b feature/daily-briefing
```

- [ ] **Step 2: Verify all existing tests pass**

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

Expected: 11 passed

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "chore: start daily-briefing feature branch"
```

---

## Task 2: Add OAuth Scopes and `CalendarClient.get_events_for_date`

**Files:**
- Modify: `src/assistant/integrations/base.py`
- Modify: `src/assistant/integrations/calendar.py`
- Create: `tests/integrations/test_calendar.py`

### Background

`GoogleAuthManager` in `base.py` holds the master list of OAuth scopes shared by all integrations. Adding a scope here means the next OAuth flow (after deleting `token.json`) will request it. `drive.file` is the minimal Drive scope — it only grants access to files the app creates, not the user's entire Drive.

`CalendarClient.get_events_for_date` is a new method that queries with a `timeMin`/`timeMax` bracketing a single day (midnight to 23:59:59 UTC), returning events in start-time order.

- [ ] **Step 1: Write failing tests for `get_events_for_date`**

Create `tests/integrations/test_calendar.py`:

```python
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
    """get_events_for_date() calls the API with timeMin at midnight and timeMax at 23:59:59."""
    calendar_client._service.events().list().execute.return_value = {"items": []}

    calendar_client.get_events_for_date(date(2026, 4, 21))

    list_call = calendar_client._service.events.return_value.list
    kwargs = list_call.call_args.kwargs
    assert kwargs["timeMin"] == "2026-04-21T00:00:00+00:00"
    assert kwargs["timeMax"] == "2026-04-21T23:59:59+00:00"


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/integrations/test_calendar.py -v
```

Expected: FAIL with `AttributeError: 'CalendarClient' object has no attribute 'get_events_for_date'`

- [ ] **Step 3: Add two new OAuth scopes to `base.py`**

Current `SCOPES` in `src/assistant/integrations/base.py`:
```python
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
```

Replace with:
```python
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]
```

- [ ] **Step 4: Add `get_events_for_date` to `CalendarClient`**

Current imports at top of `src/assistant/integrations/calendar.py`:
```python
from datetime import datetime, timezone
```

Replace with:
```python
from datetime import date, datetime, timezone
```

Add this method to `CalendarClient`, after `get_event_by_id`:

```python
def get_events_for_date(self, target_date: date) -> list[CalendarEvent]:
    """Return all events on the given date, ordered by start time.

    Uses midnight–23:59:59 UTC as the day boundary.

    Raises:
        IntegrationError: On Calendar API failure.
    """
    time_min = datetime(
        target_date.year, target_date.month, target_date.day, 0, 0, 0,
        tzinfo=timezone.utc,
    )
    time_max = datetime(
        target_date.year, target_date.month, target_date.day, 23, 59, 59,
        tzinfo=timezone.utc,
    )
    try:
        results = (
            self._service.events()
            .list(
                calendarId="primary",
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=50,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return [self._parse_event(e) for e in results.get("items", [])]
    except HttpError as e:
        raise IntegrationError(f"Calendar API error: {e}") from e
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/integrations/test_calendar.py -v
```

Expected: 3 passed

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: 14 passed

- [ ] **Step 7: Commit**

```bash
git add src/assistant/integrations/base.py \
        src/assistant/integrations/calendar.py \
        tests/integrations/test_calendar.py
git commit -m "feat: add OAuth scopes for Docs/Drive and CalendarClient.get_events_for_date"
```

---

## Task 3: Create `DocsClient`

**Files:**
- Create: `src/assistant/integrations/docs.py`
- Create: `tests/integrations/test_docs.py`

### Background

`DocsClient` wraps two Google APIs:
- **Drive API v3** (`drive`, `v3`) — used only to create new docs (`files().create()`). The `drive.file` scope is sufficient for this.
- **Docs API v1** (`docs`, `v1`) — used to read a document's end index and insert text via `batchUpdate`.

Both APIs are already installed via `google-api-python-client`. They are built using the same credentials pattern as `GmailClient` and `CalendarClient`.

**Inserting at the end of a document:** Google Docs API requires knowing the current end index. We fetch the document (`documents().get()`), read `doc["body"]["content"][-1]["endIndex"]`, subtract 1 (the last element's endIndex is past the final newline/paragraph marker), and insert there.

- [ ] **Step 1: Write failing tests**

Create `tests/integrations/test_docs.py`:

```python
"""Tests for DocsClient."""

from unittest.mock import MagicMock, patch

import pytest

from assistant.exceptions import IntegrationError
from assistant.integrations.docs import DocsClient


@pytest.fixture
def mock_auth_manager():
    manager = MagicMock()
    manager.get_credentials.return_value = MagicMock()
    return manager


@pytest.fixture
def docs_client(mock_auth_manager):
    with patch("assistant.integrations.docs.build"):
        return DocsClient(mock_auth_manager)


def test_create_doc_returns_id_and_url(docs_client):
    """create_doc() returns the doc ID and URL from the Drive API response."""
    docs_client._drive.files().create().execute.return_value = {
        "id": "abc123",
        "webViewLink": "https://docs.google.com/document/d/abc123/edit",
    }

    doc_id, doc_url = docs_client.create_doc("Personal Assistant — Daily Briefings")

    assert doc_id == "abc123"
    assert "abc123" in doc_url


def test_create_doc_raises_integration_error_on_failure(docs_client):
    """create_doc() raises IntegrationError when Drive API fails."""
    from googleapiclient.errors import HttpError

    resp = MagicMock()
    resp.status = 500
    docs_client._drive.files().create().execute.side_effect = HttpError(
        resp=resp, content=b"Server error"
    )

    with pytest.raises(IntegrationError, match="Failed to create Google Doc"):
        docs_client.create_doc("My Doc")


def test_append_section_calls_batch_update(docs_client):
    """append_section() fetches document end index and calls batchUpdate."""
    docs_client._docs.documents().get().execute.return_value = {
        "body": {"content": [{"endIndex": 1}, {"endIndex": 100}]}
    }
    docs_client._docs.documents().batchUpdate().execute.return_value = {}

    docs_client.append_section("doc123", "Hello world\n")

    docs_client._docs.documents.return_value.batchUpdate.assert_called_once()


def test_append_section_raises_integration_error_on_404(docs_client):
    """append_section() raises IntegrationError with helpful message when doc is not found."""
    from googleapiclient.errors import HttpError

    resp = MagicMock()
    resp.status = 404
    docs_client._docs.documents().get().execute.side_effect = HttpError(
        resp=resp, content=b"Not found"
    )

    with pytest.raises(IntegrationError, match="Google Doc not found"):
        docs_client.append_section("deleted-doc-id", "content")


def test_append_section_raises_integration_error_on_other_api_failure(docs_client):
    """append_section() raises IntegrationError on non-404 API errors."""
    from googleapiclient.errors import HttpError

    resp = MagicMock()
    resp.status = 500
    docs_client._docs.documents().get().execute.side_effect = HttpError(
        resp=resp, content=b"Server error"
    )

    with pytest.raises(IntegrationError, match="Google Docs API error"):
        docs_client.append_section("doc123", "content")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/integrations/test_docs.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` — `docs.py` does not exist yet

- [ ] **Step 3: Implement `DocsClient`**

Create `src/assistant/integrations/docs.py`:

```python
"""Google Docs and Drive API integration."""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from assistant.exceptions import IntegrationError
from assistant.integrations.base import GoogleAuthManager


class DocsClient:
    """Creates and appends to Google Docs via the Docs and Drive APIs."""

    def __init__(self, auth_manager: GoogleAuthManager) -> None:
        creds = auth_manager.get_credentials()
        self._docs = build("docs", "v1", credentials=creds)
        self._drive = build("drive", "v3", credentials=creds)

    def create_doc(self, title: str) -> tuple[str, str]:
        """Create a new Google Doc and return (doc_id, doc_url).

        Uses the Drive API to create a document with the Google Docs MIME type.

        Raises:
            IntegrationError: On Drive API failure.
        """
        try:
            file_metadata = {
                "name": title,
                "mimeType": "application/vnd.google-apps.document",
            }
            doc = (
                self._drive.files()
                .create(body=file_metadata, fields="id,webViewLink")
                .execute()
            )
            return doc["id"], doc["webViewLink"]
        except HttpError as e:
            raise IntegrationError(f"Failed to create Google Doc: {e}") from e

    def append_section(self, doc_id: str, content: str) -> None:
        """Append plain text content to the end of an existing Google Doc.

        Fetches the document to determine the current end index, then inserts
        the content at that position via batchUpdate.

        Raises:
            IntegrationError: If the doc is not found (404) or on other API failures.
        """
        try:
            doc = self._docs.documents().get(documentId=doc_id).execute()
            end_index = doc["body"]["content"][-1]["endIndex"] - 1
            self._docs.documents().batchUpdate(
                documentId=doc_id,
                body={
                    "requests": [
                        {
                            "insertText": {
                                "location": {"index": end_index},
                                "text": content,
                            }
                        }
                    ]
                },
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                raise IntegrationError(
                    "Google Doc not found. Remove DAILY_BRIEFING_DOC_ID from .env "
                    "to create a new one."
                ) from e
            raise IntegrationError(f"Google Docs API error: {e}") from e
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/integrations/test_docs.py -v
```

Expected: 5 passed

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: 19 passed

- [ ] **Step 6: Commit**

```bash
git add src/assistant/integrations/docs.py tests/integrations/test_docs.py
git commit -m "feat: add DocsClient for Google Docs integration"
```

---

## Task 4: Create `DailyBriefingFeature`

**Files:**
- Create: `src/assistant/features/daily_briefing.py`
- Create: `tests/features/test_daily_briefing.py`

### Background

`DailyBriefingFeature` composes the existing `EmailActionItemsFeature` and `CalendarPrepFeature`. It instantiates them internally using the injected clients (same pattern used across the codebase). This keeps the constructor simple and the orchestration logic self-contained.

Key behaviors:
- `doc_id=None` on first run → `DocsClient.create_doc()` is called; returns the new doc_id
- `doc_id` provided on subsequent runs → skips creation, constructs the URL from the ID
- Per-event `CalendarPrepFeature` failures are caught individually; the error message is inserted inline and the feature continues with remaining events
- Email failure (`IntegrationError`) propagates up — it aborts the run before any doc write

The section format (used for assertions in tests):
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Daily Briefing — Monday, April 21, 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EMAIL ACTION ITEMS
──────────────────
<email output>

CALENDAR PREP
─────────────
Event: Standup (9:00 AM, 30 min)
<prep output>
```

- [ ] **Step 1: Write failing tests**

Create `tests/features/test_daily_briefing.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/features/test_daily_briefing.py -v
```

Expected: FAIL with `ModuleNotFoundError` — `daily_briefing.py` does not exist yet

- [ ] **Step 3: Implement `DailyBriefingFeature`**

Create `src/assistant/features/daily_briefing.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/features/test_daily_briefing.py -v
```

Expected: 6 passed

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: 25 passed

- [ ] **Step 6: Commit**

```bash
git add src/assistant/features/daily_briefing.py tests/features/test_daily_briefing.py
git commit -m "feat: add DailyBriefingFeature"
```

---

## Task 5: Wire Up the CLI

**Files:**
- Modify: `src/assistant/cli/main.py`

### Background

The `daily` subcommand wires everything together:
1. Parses `--date YYYY-MM-DD` (defaults to today)
2. Reads `DAILY_BRIEFING_DOC_ID` from env (None if not set)
3. Builds all clients including `DocsClient`
4. Calls `DailyBriefingFeature.run()`
5. On first run: appends `DAILY_BRIEFING_DOC_ID=<id>` to `.env` so subsequent runs reuse the doc
6. Prints the doc URL

Note: `_build_clients()` already returns `auth_manager` as the first element (currently discarded with `_`). The `daily` command unpacks it so it can construct `DocsClient`.

- [ ] **Step 1: Add imports to `main.py`**

Current imports section in `src/assistant/cli/main.py`:
```python
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from assistant.cli.formatters import format_event_detail, format_event_list
from assistant.exceptions import AssistantError
from assistant.features.calendar_prep import CalendarPrepFeature
from assistant.features.email_actions import EmailActionItemsFeature
from assistant.features.linkedin_feed import LinkedInFeedFeature
from assistant.integrations.linkedin import LinkedInDigestClient
from assistant.integrations.base import GoogleAuthManager
from assistant.integrations.calendar import CalendarClient
from assistant.integrations.gmail import GmailClient
from assistant.llm.claude import ClaudeClient
```

Replace with:
```python
import argparse
import os
import sys
from datetime import date as Date
from pathlib import Path

from dotenv import load_dotenv

from assistant.cli.formatters import format_event_detail, format_event_list
from assistant.exceptions import AssistantError
from assistant.features.calendar_prep import CalendarPrepFeature
from assistant.features.daily_briefing import DailyBriefingFeature
from assistant.features.email_actions import EmailActionItemsFeature
from assistant.features.linkedin_feed import LinkedInFeedFeature
from assistant.integrations.base import GoogleAuthManager
from assistant.integrations.calendar import CalendarClient
from assistant.integrations.docs import DocsClient
from assistant.integrations.gmail import GmailClient
from assistant.integrations.linkedin import LinkedInDigestClient
from assistant.llm.claude import ClaudeClient
```

- [ ] **Step 2: Add `daily` subparser to `_build_parser()`**

In `_build_parser()`, after the `linkedin` subparser block (lines that add `-- linkedin subcommand --`), add:

```python
    # -- daily subcommand --
    daily_parser = subparsers.add_parser(
        "daily", help="Generate a daily briefing and save it to Google Docs."
    )
    daily_parser.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Date to generate briefing for (default: today)",
    )
```

- [ ] **Step 3: Add `daily` command branch to `main()`**

In `main()`, the current structure is:
```python
    try:
        _, gmail_client, calendar_client, claude_client = _build_clients(api_key, args.model)

        if args.command == "email":
            ...
        elif args.command == "calendar":
            ...
        elif args.command == "linkedin":
            ...
```

Change `_` to `auth_manager` on the `_build_clients` line, and add the `daily` branch:

```python
    try:
        auth_manager, gmail_client, calendar_client, claude_client = _build_clients(api_key, args.model)

        if args.command == "email":
            feature = EmailActionItemsFeature(gmail_client, claude_client)
            print(f"\n📬 Analyzing your {args.max_emails} most recent emails...\n")
            print("=" * 60)
            for chunk in feature.run(max_emails=args.max_emails):
                print(chunk, end="", flush=True)
            print("\n" + "=" * 60)

        elif args.command == "calendar":
            if args.cal_command == "list":
                feature = CalendarPrepFeature(calendar_client, claude_client)
                events = feature.list_upcoming(max_results=args.max_events)
                print(f"\n📅 Upcoming events ({len(events)} shown):\n")
                print(format_event_list(events))
                print("\nRun `assistant calendar prep <event-id>` to prepare for an event.")

            elif args.cal_command == "prep":
                feature = CalendarPrepFeature(calendar_client, claude_client)
                event = calendar_client.get_event_by_id(args.event_id)
                print(f"\n📅 Preparing for:\n")
                print(format_event_detail(event))
                print("\n" + "=" * 60)
                for chunk in feature.run(args.event_id):
                    print(chunk, end="", flush=True)
                print("\n" + "=" * 60)

        elif args.command == "linkedin":
            linkedin_client = LinkedInDigestClient(gmail_client)
            feature = LinkedInFeedFeature(linkedin_client, claude_client)
            print(f"\n💼 LinkedIn network activity (last {args.days} days)...\n")
            print("=" * 60)
            for chunk in feature.run(days=args.days):
                print(chunk, end="", flush=True)
            print("\n" + "=" * 60)

        elif args.command == "daily":
            target_date = Date.fromisoformat(args.date) if args.date else Date.today()
            doc_id = os.getenv("DAILY_BRIEFING_DOC_ID") or None
            date_str = target_date.strftime("%A, %B %-d, %Y")

            docs_client = DocsClient(auth_manager)
            feature = DailyBriefingFeature(gmail_client, calendar_client, claude_client, docs_client)

            print(f"\n📋 Generating daily briefing for {date_str}...")
            print("=" * 60)

            returned_doc_id, doc_url = feature.run(target_date, doc_id)

            if doc_id is None:
                env_path = _PROJECT_ROOT / ".env"
                with open(env_path, "a") as f:
                    f.write(f"DAILY_BRIEFING_DOC_ID={returned_doc_id}\n")
                print("\n✅ Created new Google Doc and saved ID to .env")

            print(f"\n✅ Briefing written to: {doc_url}")
            print("=" * 60)
```

- [ ] **Step 4: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: 25 passed (no new tests for CLI wiring; the feature logic is already tested)

- [ ] **Step 5: Commit**

```bash
git add src/assistant/cli/main.py
git commit -m "feat: add daily subcommand to CLI"
```

---

## Task 6: Re-auth, Smoke Test, Push, and PR

**Files:** none (runtime + git operations)

### Background

The new OAuth scopes (`documents`, `drive.file`) were added to `SCOPES` in Task 2. The existing `token.json` was issued before these scopes were added, so it won't have permission to call the Docs or Drive APIs. You must delete it so the OAuth flow re-runs and requests all four scopes.

- [ ] **Step 1: Delete `token.json` to force re-authorization**

```bash
rm token.json
```

- [ ] **Step 2: Run `assistant daily` to trigger re-auth and smoke-test**

```bash
source venv/bin/activate
assistant daily
```

Your browser will open for OAuth. Grant all requested permissions (Gmail, Calendar, Google Docs, Drive). After auth:
- The CLI should print `📋 Generating daily briefing for <today>...`
- It should print `✅ Created new Google Doc and saved ID to .env`
- It should print `✅ Briefing written to: https://docs.google.com/document/d/...`
- Opening that URL should show a Google Doc with a dated briefing section

- [ ] **Step 3: Verify `DAILY_BRIEFING_DOC_ID` was saved to `.env`**

```bash
grep DAILY_BRIEFING_DOC_ID .env
```

Expected: `DAILY_BRIEFING_DOC_ID=<some-id>`

- [ ] **Step 4: Run `assistant daily` a second time to verify append behavior**

```bash
assistant daily
```

Expected:
- No browser OAuth prompt (token already valid)
- No "Created new Google Doc" message
- Doc URL printed again
- Opening the doc shows a second dated section appended below the first

- [ ] **Step 5: Push branch and open PR**

```bash
git push -u origin feature/daily-briefing
gh pr create \
  --title "feat: daily briefing command writes email + calendar prep to Google Docs" \
  --body "$(cat <<'EOF'
## Summary

- Adds \`assistant daily [--date YYYY-MM-DD]\` command
- Runs email action items + calendar prep for all events on the given day
- Appends a dated section to a persistent Google Doc (creates on first run, appends on subsequent runs)
- Doc ID persisted to \`.env\` as \`DAILY_BRIEFING_DOC_ID\`

## New files
- \`src/assistant/integrations/docs.py\` — DocsClient (Drive + Docs APIs)
- \`src/assistant/features/daily_briefing.py\` — DailyBriefingFeature
- \`tests/integrations/test_calendar.py\`
- \`tests/integrations/test_docs.py\`
- \`tests/features/test_daily_briefing.py\`

## Test plan
- [ ] \`assistant daily\` — creates new doc, saves ID to .env, prints URL
- [ ] \`assistant daily\` again — appends second section, no new doc created
- [ ] \`assistant daily --date 2026-04-20\` — generates for a specific date
- [ ] All 25 tests pass: \`python -m pytest tests/ -v\`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```


# Daily Briefing Feature Design

## Goal

Run email action items and calendar prep for all events on a given day, then append a dated section to a persistent Google Doc — creating the doc on first run and reusing it on subsequent runs.

## Architecture

Four changes to the codebase:

| File | Change |
|------|--------|
| `src/assistant/integrations/docs.py` | New — `DocsClient` wrapping Google Docs + Drive APIs |
| `src/assistant/features/daily_briefing.py` | New — `DailyBriefingFeature` orchestrating the run |
| `src/assistant/integrations/base.py` | Modify — add `documents` and `drive.file` OAuth scopes |
| `src/assistant/cli/main.py` | Modify — add `daily` subcommand with `--date` flag |

**Tech stack additions:** Google Docs API (`docs`, `v1`), Google Drive API (`drive`, `v3`) — both via `google-api-python-client`, already a dependency.

---

## Components

### `DocsClient` (`src/assistant/integrations/docs.py`)

Wraps the Docs and Drive APIs. Two responsibilities only:

1. **`create_doc(title: str) -> tuple[str, str]`** — Creates a new Google Doc via Drive API, returns `(doc_id, doc_url)`.
2. **`append_section(doc_id: str, content: str) -> None`** — Appends formatted content to the end of an existing doc. Fetches the document to get its current end index, then calls `documents.batchUpdate` with an `insertText` request at that index.

No formatting logic lives here — receives pre-formatted plain text.

### `DocsClient` OAuth scopes (added to `base.py`)

```python
"https://www.googleapis.com/auth/documents",
"https://www.googleapis.com/auth/drive.file",
```

`drive.file` is the minimal Drive scope — grants access only to files created or opened by the app, not the user's entire Drive.

### `CalendarClient.get_events_for_date` (new method on existing class)

```python
def get_events_for_date(self, date: date) -> list[CalendarEvent]
```

Queries with `timeMin = date at 00:00:00 UTC` and `timeMax = date at 23:59:59 UTC`. Returns events ordered by start time.

### `DailyBriefingFeature` (`src/assistant/features/daily_briefing.py`)

Constructor: `(gmail_client, calendar_client, claude_client, docs_client)`

Single public method:

```python
def run(self, date: date, doc_id: str | None) -> tuple[str, str]
```

Returns `(doc_id, doc_url)`. The `doc_id` parameter is `None` on first run.

**Execution steps:**
1. Collect email action items: consume `EmailActionItemsFeature.run()` into a string
2. Fetch all events for the date via `CalendarClient.get_events_for_date(date)`
3. For each event, consume `CalendarPrepFeature.run(event_id)` into a string; on per-event failure, use a fallback string noting the error
4. Build the full section string (see format below)
5. If `doc_id` is `None`: call `DocsClient.create_doc(title)` to get `(doc_id, doc_url)`; caller is responsible for persisting the ID
6. Call `DocsClient.append_section(doc_id, content)`
7. Return `(doc_id, doc_url)`

### CLI — `daily` subcommand (`src/assistant/cli/main.py`)

```
assistant daily [--date YYYY-MM-DD]
```

- `--date`: defaults to today (`date.today()`)
- Reads `DAILY_BRIEFING_DOC_ID` from environment (`.env`)
- On first run (no ID in env): after `DailyBriefingFeature.run()` returns, appends `DAILY_BRIEFING_DOC_ID=<id>` to `.env` and prints the doc URL
- Streams progress to terminal as each step completes

---

## Data Flow

```
CLI
 └─ DailyBriefingFeature.run(date, doc_id)
     ├─ EmailActionItemsFeature.run()        → email_output: str
     ├─ CalendarClient.get_events_for_date() → events: list[CalendarEvent]
     ├─ CalendarPrepFeature.run(event_id)    → per-event prep: str  (× N events)
     ├─ build section string
     └─ DocsClient.append_section(doc_id, content)
         └─ documents.batchUpdate insertText
```

---

## Doc Section Format

Each run appends the following block to the Google Doc:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Daily Briefing — Monday, April 21, 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EMAIL ACTION ITEMS
──────────────────
[email action items output]


CALENDAR PREP
─────────────
Event: Standup (9:00 AM, 30 min)
[calendar prep output for Standup]

Event: 1:1 with Alex (2:00 PM, 60 min)
[calendar prep output for 1:1]
```

If there are no events: the Calendar Prep section contains "No events scheduled for this day."

---

## Doc ID Persistence

- Stored as `DAILY_BRIEFING_DOC_ID` in `.env` (already gitignored)
- On first run: `DailyBriefingFeature` returns the new `doc_id`; CLI appends `DAILY_BRIEFING_DOC_ID=<id>\n` to `.env`
- On subsequent runs: CLI reads `DAILY_BRIEFING_DOC_ID` from env and passes it to the feature
- If the doc was deleted and the Docs API returns 404: `DocsClient.append_section` raises `IntegrationError` with message "Google Doc not found. Remove DAILY_BRIEFING_DOC_ID from .env to create a new one."

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No events on target date | Writes "No events scheduled" in Calendar Prep section — not an error |
| Individual event prep fails | Inserts `[Error generating prep for this event: <message>]` in that event's slot; continues |
| Doc create/append fails | Raises `IntegrationError`, caught by CLI, printed to stderr |
| Doc deleted (404) | Raises `IntegrationError` with instructions to reset `DAILY_BRIEFING_DOC_ID` |
| Email feature fails | Raises `IntegrationError`, aborts the run before writing anything |

---

## Testing

All external clients mocked. Tests live in `tests/features/test_daily_briefing.py` and `tests/integrations/test_docs.py`.

**`DailyBriefingFeature` tests:**
- First-run path: `doc_id=None` → `DocsClient.create_doc` called, returned ID passed back
- Subsequent-run path: `doc_id` provided → `DocsClient.create_doc` not called
- Email output appears in section content
- Each event's prep output appears in section content under correct header
- Zero events → "No events scheduled" in section
- Per-event prep failure → error note inserted, other events still processed

**`DocsClient` tests:**
- `create_doc` calls Drive API with correct parameters, returns `(id, url)`
- `append_section` calls `documents.batchUpdate` with `insertText` at correct index
- `append_section` raises `IntegrationError` on 404

**`CalendarClient.get_events_for_date` tests:**
- Calls API with correct `timeMin`/`timeMax` for the given date
- Returns events ordered by start time

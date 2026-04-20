# Personal Assistant — Claude Code Guide

## Project overview

A personal AI assistant CLI powered by Claude. Reads Gmail, Google Calendar, and LinkedIn digest emails to surface action items, prep notes, and a daily briefing written to a Google Doc.

```
assistant email                      # email action items
assistant calendar list              # upcoming events
assistant calendar prep <event-id>   # prep notes for one event
assistant linkedin [--days N]        # LinkedIn network summary
assistant daily [--date YYYY-MM-DD]  # full daily briefing → Google Doc
```

## Architecture

Three-layer structure under `src/assistant/`:

```
integrations/   Data access — wraps external APIs, returns dataclasses
features/       Business logic — composes integrations + Claude, returns Iterator[str]
cli/            Presentation — parses args, streams feature output to stdout
llm/            Claude API wrapper (only file that imports anthropic)
```

**Rule:** features never print; the CLI handles all I/O. Integrations never call Claude.

## Setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e .
cp .env.example .env   # add ANTHROPIC_API_KEY
# place credentials.json from Google Cloud Console in project root
assistant email        # triggers OAuth on first run, saves token.json
```

**Required Google APIs** (enable in Cloud Console):
- Gmail API
- Google Calendar API
- Google Docs API
- Google Drive API

## Environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `DAILY_BRIEFING_DOC_ID` | Auto-set | Written by `assistant daily` on first run |

## Running tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

All external APIs are mocked. No credentials needed to run tests.

## Key patterns

### Adding a new integration

1. Create `src/assistant/integrations/<name>.py`
2. Accept `GoogleAuthManager` (or another client) in `__init__`
3. Return dataclasses, raise `IntegrationError` on API failures
4. Add any new OAuth scopes to `SCOPES` in `src/assistant/integrations/base.py`
5. Delete `token.json` on next run to re-authorize with new scopes

### Adding a new feature

1. Create `src/assistant/features/<name>.py`
2. Accept clients in `__init__`, implement `run(...) -> Iterator[str]`
3. Wire into `src/assistant/cli/main.py` — add subparser + command branch

### Google OAuth scopes

All scopes are centralized in `SCOPES` in `src/assistant/integrations/base.py`. Adding a scope there applies to all integrations (they share one `token.json`). After changing scopes, delete `token.json` to force re-authorization.

### Claude client

`src/assistant/llm/claude.py` — `ClaudeClient.stream_response(system_prompt, user_message) -> Iterator[str]`. Default model: `claude-opus-4-6`. Default `max_tokens`: 4096. No other file imports `anthropic`.

## User context (used in Claude prompts)

The user works in software engineering leadership (previously Spotify, currently Keebo). Manages engineering teams; cares about software engineering trends, leadership, AI, and the tech industry. This context is embedded in the system prompts in `calendar_prep.py` and `linkedin_feed.py`.

## File reference

| File | Responsibility |
|------|---------------|
| `integrations/base.py` | `GoogleAuthManager` — shared OAuth for all Google APIs |
| `integrations/gmail.py` | `GmailClient` — fetch/search emails |
| `integrations/calendar.py` | `CalendarClient` — fetch events, get by ID, get by date |
| `integrations/linkedin.py` | `LinkedInDigestClient` — searches Gmail for LinkedIn digests |
| `integrations/docs.py` | `DocsClient` — create Google Docs, append text sections |
| `features/email_actions.py` | `EmailActionItemsFeature` — 2-3 email action items via Claude |
| `features/calendar_prep.py` | `CalendarPrepFeature` — prep notes for a calendar event |
| `features/linkedin_feed.py` | `LinkedInFeedFeature` — trending themes + worth-your-attention from LinkedIn digests |
| `features/daily_briefing.py` | `DailyBriefingFeature` — orchestrates email + calendar prep, writes to Google Doc |
| `cli/main.py` | Argument parsing, client construction, feature dispatch |
| `cli/formatters.py` | Pure formatting functions for calendar event display |
| `exceptions.py` | Exception hierarchy: `AssistantError` → `IntegrationError`, `LLMError`, etc. |
| `llm/claude.py` | `ClaudeClient` — only file that imports `anthropic` |

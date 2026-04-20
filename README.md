# Personal Assistant

A personal AI assistant CLI powered by Claude. Connects to Gmail, Google Calendar, and LinkedIn to surface action items, generate prep notes, and write a daily briefing to a Google Doc.

## Commands

```bash
assistant email                       # 2-3 action items from recent emails
assistant calendar list               # upcoming calendar events
assistant calendar prep <event-id>    # prep notes for a specific event
assistant linkedin [--days N]         # LinkedIn network summary (default: 14 days)
assistant daily [--date YYYY-MM-DD]   # full daily briefing written to Google Docs
```

## Setup

### 1. Clone and install

```bash
git clone https://github.com/lfoos/personal-assistant.git
cd personal-assistant
python3 -m venv venv && source venv/bin/activate
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
```

Add your Anthropic API key to `.env`:
```
ANTHROPIC_API_KEY=your_key_here
```

### 3. Set up Google APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com) and create a project
2. Enable these APIs:
   - Gmail API
   - Google Calendar API
   - Google Docs API
   - Google Drive API
3. Go to **APIs & Services → Credentials → Create OAuth 2.0 Client ID** (Desktop app)
4. Download the credentials JSON and save it as `credentials.json` in the project root

### 4. Authorize

Run any command — your browser will open for Google OAuth on the first run:

```bash
assistant email
```

Credentials are saved to `token.json` for subsequent runs.

## Daily Briefing

The `daily` command combines email action items and calendar prep for every event on a given day, then appends a dated section to a persistent Google Doc:

```bash
assistant daily             # today's briefing
assistant daily --date 2026-04-21   # specific date
```

On first run, a new Google Doc is created and its ID is saved to `.env` as `DAILY_BRIEFING_DOC_ID`. Every subsequent run appends a new section to the same doc.

## Running Tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

All external APIs are mocked — no credentials needed.

## Project Structure

```
src/assistant/
├── integrations/   # Google API clients (Gmail, Calendar, Docs, LinkedIn)
├── features/       # Business logic — composes integrations + Claude
├── cli/            # Argument parsing and output
├── llm/            # Claude API wrapper
└── exceptions.py   # Custom exception hierarchy
```

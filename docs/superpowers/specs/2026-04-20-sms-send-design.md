# SMS Send Feature Design

## Goal

Add a text message sending capability that delivers a Claude-summarized version of any feature's output directly to the user via SMS. Integrates as both a `--sms` flag on existing commands and a standalone `assistant sms <subcommand>`.

## Architecture

Three changes to the codebase:

| File | Change |
|------|--------|
| `src/assistant/integrations/sms.py` | New — `SmsClient` wrapping boto3 SNS |
| `src/assistant/features/sms_send.py` | New — `SmsSendFeature` orchestrating summarize → send |
| `src/assistant/cli/main.py` | Modify — add `--sms` flag to existing subcommands + `sms` subcommand |

**Tech stack additions:** `boto3` added to `pyproject.toml`. AWS credentials via standard boto3 credential chain (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`). New env var: `RECIPIENT_PHONE_NUMBER` in `.env`.

---

## Components

### `SmsClient` (`src/assistant/integrations/sms.py`)

Wraps boto3 SNS. Uses the standard boto3 credential chain — no `GoogleAuthManager` involved.

Single method: `send(to: str, body: str) -> None`

- Calls `boto3.client("sns").publish(PhoneNumber=to, Message=body)`
- Raises `IntegrationError` on `botocore.exceptions.ClientError`

### `SmsSendFeature` (`src/assistant/features/sms_send.py`)

Constructor: `(claude_client: ClaudeClient, sms_client: SmsClient)`

Single method: `run(content: str, to: str) -> Iterator[str]`

**Execution steps:**
1. Call `ClaudeClient.stream_response(system_prompt, content)` and collect into a summary string
2. Call `SmsClient.send(to, summary)`
3. Yield `f"✅ SMS sent to {to}"`

**Summarization prompt:** The system prompt instructs Claude to extract the 3–5 most important action items or insights from the assistant output, written in plain text (no markdown), under 1200 characters. This keeps messages within safe SMS length limits while preserving the most actionable content.

### CLI — `--sms` flag (`src/assistant/cli/main.py`)

Added to: `email`, `calendar prep`, `linkedin`, `daily`.

Behavior: runs the feature normally (streams to stdout), then collects the full output and passes it to `SmsSendFeature.run(content, to)`. The SMS confirmation is printed after the normal output.

### CLI — `assistant sms <subcommand>` (`src/assistant/cli/main.py`)

A new top-level `sms` subcommand that accepts the same arguments as the underlying command:

```
assistant sms email [--max-emails N]
assistant sms calendar prep <event-id>
assistant sms linkedin [--days N]
assistant sms daily [--date YYYY-MM-DD]
```

Behavior: runs the feature, collects output into a string (does **not** print to stdout), then calls `SmsSendFeature.run(content, to)`. Prints only the confirmation line.

---

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `RECIPIENT_PHONE_NUMBER` | Yes | E.164 format, e.g. `+15551234567` |
| `AWS_ACCESS_KEY_ID` | Yes | Standard boto3 credential chain |
| `AWS_SECRET_ACCESS_KEY` | Yes | Standard boto3 credential chain |
| `AWS_DEFAULT_REGION` | Yes | Must be a region with SNS SMS enabled (e.g. `us-east-1`) |

---

## Data Flow

```
--sms flag path:
CLI runs feature → collects Iterator[str] into string → prints to stdout
  └─ SmsSendFeature.run(content, to)
      ├─ ClaudeClient.stream_response(system, content) → summary: str
      └─ SmsClient.send(to, summary)
          └─ sns.publish(PhoneNumber, Message)

sms subcommand path:
CLI runs feature → collects Iterator[str] into string (no stdout print)
  └─ SmsSendFeature.run(content, to) → yields "✅ SMS sent to <number>"
      └─ (same as above)
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `RECIPIENT_PHONE_NUMBER` not set | `ConfigurationError` raised before running feature |
| AWS credentials missing/invalid | `IntegrationError` from `SmsClient`, printed to stderr |
| SNS `ClientError` (bad number, quota, etc.) | `IntegrationError` with SNS error message |
| Feature fails before SMS send | Error propagates normally; SMS never attempted |

---

## Testing

All external clients mocked. Tests live in `tests/integrations/test_sms.py` and `tests/features/test_sms_send.py`.

**`SmsClient` tests:**
- `send()` calls `sns.publish()` with correct `PhoneNumber` and `Message`
- `send()` raises `IntegrationError` on `ClientError`

**`SmsSendFeature` tests:**
- Claude summary is passed to `sms_client.send()` as the message body
- `to` parameter is passed through correctly
- Confirmation string is yielded after send
- `IntegrationError` from `sms_client.send()` propagates

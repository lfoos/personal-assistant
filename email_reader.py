"""Gmail API integration for reading recent emails."""

import base64
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = Path(__file__).parent / "token.json"
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"


def get_gmail_service():
    """Authenticate and return a Gmail API service instance."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    "credentials.json not found. Download it from Google Cloud Console "
                    "(APIs & Services > Credentials > OAuth 2.0 Client ID)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _decode_body(payload: dict) -> str:
    """Extract plain text body from a Gmail message payload."""
    body = ""

    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    elif "parts" in payload:
        for part in payload["parts"]:
            body += _decode_body(part)

    return body


def get_recent_emails(max_results: int = 20) -> list[dict]:
    """
    Fetch the most recent emails from the inbox.

    Returns a list of dicts with keys: subject, sender, date, snippet, body.
    """
    service = get_gmail_service()

    results = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        maxResults=max_results,
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me",
            id=msg_ref["id"],
            format="full",
        ).execute()

        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body = _decode_body(msg["payload"])

        emails.append({
            "subject": headers.get("Subject", "(no subject)"),
            "sender": headers.get("From", "unknown"),
            "date": headers.get("Date", "unknown"),
            "snippet": msg.get("snippet", ""),
            "body": body[:3000],  # cap body length per email
        })

    return emails

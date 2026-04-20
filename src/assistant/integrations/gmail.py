"""Gmail API integration."""

import base64
from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from assistant.exceptions import IntegrationError
from assistant.integrations.base import GoogleAuthManager


@dataclass
class EmailMessage:
    subject: str
    sender: str
    date: str
    snippet: str
    body: str


class GmailClient:
    """Fetches messages from the authenticated user's Gmail inbox."""

    _BODY_CHAR_LIMIT = 3000

    def __init__(self, auth_manager: GoogleAuthManager) -> None:
        creds = auth_manager.get_credentials()
        self._service = build("gmail", "v1", credentials=creds)

    def get_recent_messages(self, max_results: int = 20) -> list[EmailMessage]:
        """Return the most recent inbox messages.

        Raises:
            IntegrationError: On Gmail API failure.
        """
        try:
            results = (
                self._service.users()
                .messages()
                .list(userId="me", labelIds=["INBOX"], maxResults=max_results)
                .execute()
            )
            messages = results.get("messages", [])
            return [self._fetch_message(m["id"]) for m in messages]
        except HttpError as e:
            raise IntegrationError(f"Gmail API error: {e}") from e

    def search_messages(self, query: str, max_results: int = 20) -> list[EmailMessage]:
        """Search messages using a Gmail query string.

        Args:
            query: Gmail search query (e.g. 'from:linkedin.com subject:digest')
            max_results: Maximum number of messages to return.

        Raises:
            IntegrationError: On Gmail API failure.
        """
        try:
            results = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            messages = results.get("messages", [])
            return [self._fetch_message(m["id"]) for m in messages]
        except HttpError as e:
            raise IntegrationError(f"Gmail API error: {e}") from e

    def _fetch_message(self, message_id: str) -> EmailMessage:
        msg = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body = self._decode_body(msg["payload"])

        return EmailMessage(
            subject=headers.get("Subject", "(no subject)"),
            sender=headers.get("From", "unknown"),
            date=headers.get("Date", "unknown"),
            snippet=msg.get("snippet", ""),
            body=body[: self._BODY_CHAR_LIMIT],
        )

    def _decode_body(self, payload: dict) -> str:
        body = ""
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif "parts" in payload:
            for part in payload["parts"]:
                body += self._decode_body(part)
        return body

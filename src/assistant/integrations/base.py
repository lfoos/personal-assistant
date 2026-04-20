"""Shared Google OAuth management for all integrations."""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from assistant.exceptions import AuthenticationError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleAuthManager:
    """Manages the Google OAuth lifecycle, shared across all integrations.

    Centralizing scope management here means all integrations share a single
    token file. Adding a new integration only requires appending to SCOPES.
    """

    def __init__(self, credentials_path: Path, token_path: Path) -> None:
        self._credentials_path = credentials_path
        self._token_path = token_path

    def get_credentials(self) -> Credentials:
        """Return valid Google credentials, running the OAuth flow if needed.

        Raises:
            AuthenticationError: If credentials.json is missing.
        """
        creds = None

        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self._token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self._credentials_path.exists():
                    raise AuthenticationError(
                        f"credentials.json not found at {self._credentials_path}. "
                        "Download it from Google Cloud Console "
                        "(APIs & Services → Credentials → OAuth 2.0 Client ID)."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self._credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(self._token_path, "w") as f:
                f.write(creds.to_json())

        return creds

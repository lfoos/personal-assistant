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

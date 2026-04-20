"""LinkedIn digest email integration.

APPROACH: LinkedIn's official API does not provide a network feed endpoint for
individual developers — it requires business accounts and special partnership
access. This integration reads LinkedIn's automated digest emails from Gmail
as a workaround.

TODO: Replace with a proper LinkedIn API or approved third-party service
(e.g. ProxyCurl) once a viable option becomes available.
See: https://github.com/lfoos/personal-assistant
"""

from datetime import date, timedelta

from assistant.integrations.gmail import EmailMessage, GmailClient

# Gmail query to find LinkedIn digest emails.
# Uses domain matching for all @linkedin.com senders and filters by
# subject keywords common to digest-style notifications.
_LINKEDIN_QUERY_TEMPLATE = (
    "from:(linkedin.com) "
    "subject:(digest OR \"posts in your network\" OR \"missed\" OR \"trending\" OR \"your network\") "
    "after:{after_date}"
)


class LinkedInDigestClient:
    """Finds LinkedIn network digest emails via Gmail search.

    Composes GmailClient rather than subclassing — it adds LinkedIn-specific
    search logic without coupling to Gmail's authentication or API details.
    """

    def __init__(self, gmail_client: GmailClient) -> None:
        self._gmail = gmail_client

    def get_digest_emails(self, days: int = 14) -> list[EmailMessage]:
        """Return LinkedIn digest emails from the last N days.

        Args:
            days: How many days back to search (default 14).

        Returns:
            List of EmailMessage objects. Empty list if none found.
        """
        after_date = (date.today() - timedelta(days=days)).strftime("%Y/%m/%d")
        query = _LINKEDIN_QUERY_TEMPLATE.format(after_date=after_date)
        return self._gmail.search_messages(query=query, max_results=25)

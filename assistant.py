#!/usr/bin/env python3
"""Personal AI assistant — reads recent emails and surfaces 2-3 action items."""

import os
import sys

import anthropic
from dotenv import load_dotenv

from email_reader import get_recent_emails

load_dotenv()

SYSTEM_PROMPT = """You are a personal productivity assistant. Your job is to review
a person's recent emails and identify the 2-3 most important action items they need
to address. Focus on:
- Emails requiring a response or decision
- Time-sensitive requests or deadlines
- Important tasks assigned to them
- Anything that could have negative consequences if ignored

Be concise and specific. For each action item, include:
1. What needs to be done
2. Who it involves (if relevant)
3. Any deadline or urgency level

Ignore newsletters, promotional emails, and automated notifications unless they
contain something genuinely important."""


def format_emails_for_prompt(emails: list[dict]) -> str:
    """Format a list of email dicts into a readable prompt block."""
    parts = []
    for i, email in enumerate(emails, 1):
        parts.append(
            f"--- Email {i} ---\n"
            f"From: {email['sender']}\n"
            f"Date: {email['date']}\n"
            f"Subject: {email['subject']}\n"
            f"Body:\n{email['body'] or email['snippet']}\n"
        )
    return "\n".join(parts)


def get_action_items(emails: list[dict]) -> None:
    """Send emails to Claude and stream 2-3 action items."""
    client = anthropic.Anthropic()

    email_text = format_emails_for_prompt(emails)
    user_message = (
        f"Here are my {len(emails)} most recent emails. "
        f"Please identify the 2-3 most important action items I need to address.\n\n"
        f"{email_text}"
    )

    print("\n📬 Analyzing your recent emails...\n")
    print("=" * 60)

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print("\n" + "=" * 60)


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    try:
        print("Fetching recent emails from Gmail...")
        emails = get_recent_emails(max_results=20)

        if not emails:
            print("No emails found in your inbox.")
            return

        print(f"Retrieved {len(emails)} recent emails.")
        get_action_items(emails)

    except FileNotFoundError as e:
        print(f"\nSetup required: {e}")
        print("\nTo set up Gmail access:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project and enable the Gmail API")
        print("3. Create OAuth 2.0 credentials (Desktop app)")
        print("4. Download credentials.json and place it in this directory")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

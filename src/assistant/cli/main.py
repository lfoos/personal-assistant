"""CLI entry point — argument parsing and feature dispatch."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from assistant.cli.formatters import format_event_detail, format_event_list
from assistant.exceptions import AssistantError
from assistant.features.calendar_prep import CalendarPrepFeature
from assistant.features.email_actions import EmailActionItemsFeature
from assistant.features.linkedin_feed import LinkedInFeedFeature
from assistant.integrations.linkedin import LinkedInDigestClient
from assistant.integrations.base import GoogleAuthManager
from assistant.integrations.calendar import CalendarClient
from assistant.integrations.gmail import GmailClient
from assistant.llm.claude import ClaudeClient

_PROJECT_ROOT = Path(__file__).parents[3]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assistant",
        description="Personal AI assistant powered by Claude.",
    )
    parser.add_argument(
        "--model",
        default=ClaudeClient.DEFAULT_MODEL,
        help=f"Claude model to use (default: {ClaudeClient.DEFAULT_MODEL})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- email subcommand --
    email_parser = subparsers.add_parser("email", help="Summarize action items from recent emails.")
    email_parser.add_argument(
        "--max-emails", type=int, default=20, metavar="N",
        help="Number of recent emails to analyze (default: 20)",
    )

    # -- calendar subcommand --
    cal_parser = subparsers.add_parser("calendar", help="Calendar event preparation.")
    cal_sub = cal_parser.add_subparsers(dest="cal_command", required=True)

    list_parser = cal_sub.add_parser("list", help="List upcoming calendar events.")
    list_parser.add_argument(
        "--max-events", type=int, default=10, metavar="N",
        help="Number of upcoming events to show (default: 10)",
    )

    prep_parser = cal_sub.add_parser("prep", help="Generate preparation notes for an event.")
    prep_parser.add_argument("event_id", help="Google Calendar event ID (from `assistant calendar list`)")

    # -- linkedin subcommand --
    linkedin_parser = subparsers.add_parser("linkedin", help="Summarize LinkedIn network activity from digest emails.")
    linkedin_parser.add_argument(
        "--days", type=int, default=14, metavar="N",
        help="Number of days of digest emails to look back (default: 14)",
    )

    return parser


def _build_clients(api_key: str, model: str) -> tuple[GoogleAuthManager, GmailClient, CalendarClient, ClaudeClient]:
    auth_manager = GoogleAuthManager(
        credentials_path=_PROJECT_ROOT / "credentials.json",
        token_path=_PROJECT_ROOT / "token.json",
    )
    return (
        auth_manager,
        GmailClient(auth_manager),
        CalendarClient(auth_manager),
        ClaudeClient(api_key=api_key, model=model),
    )


def main() -> None:
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set. Add it to your .env file.", file=sys.stderr)
        sys.exit(1)

    parser = _build_parser()
    args = parser.parse_args()

    try:
        _, gmail_client, calendar_client, claude_client = _build_clients(api_key, args.model)

        if args.command == "email":
            feature = EmailActionItemsFeature(gmail_client, claude_client)
            print(f"\n📬 Analyzing your {args.max_emails} most recent emails...\n")
            print("=" * 60)
            for chunk in feature.run(max_emails=args.max_emails):
                print(chunk, end="", flush=True)
            print("\n" + "=" * 60)

        elif args.command == "calendar":
            if args.cal_command == "list":
                feature = CalendarPrepFeature(calendar_client, claude_client)
                events = feature.list_upcoming(max_results=args.max_events)
                print(f"\n📅 Upcoming events ({len(events)} shown):\n")
                print(format_event_list(events))
                print("\nRun `assistant calendar prep <event-id>` to prepare for an event.")

            elif args.cal_command == "prep":
                feature = CalendarPrepFeature(calendar_client, claude_client)
                # Fetch event details for the header before streaming
                event = calendar_client.get_event_by_id(args.event_id)
                print(f"\n📅 Preparing for:\n")
                print(format_event_detail(event))
                print("\n" + "=" * 60)
                for chunk in feature.run(args.event_id):
                    print(chunk, end="", flush=True)
                print("\n" + "=" * 60)

        elif args.command == "linkedin":
            linkedin_client = LinkedInDigestClient(gmail_client)
            feature = LinkedInFeedFeature(linkedin_client, claude_client)
            print(f"\n💼 LinkedIn network activity (last {args.days} days)...\n")
            print("=" * 60)
            for chunk in feature.run(days=args.days):
                print(chunk, end="", flush=True)
            print("\n" + "=" * 60)

    except AssistantError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(0)

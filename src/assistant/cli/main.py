"""CLI entry point — argument parsing and feature dispatch."""

import argparse
import os
import sys
from datetime import date as Date
from pathlib import Path

from dotenv import load_dotenv

from assistant.cli.formatters import format_event_detail, format_event_list
from assistant.exceptions import AssistantError, ConfigurationError
from assistant.features.sms_send import SmsSendFeature
from assistant.integrations.sms import SmsClient
from assistant.features.calendar_prep import CalendarPrepFeature
from assistant.features.daily_briefing import DailyBriefingFeature
from assistant.features.email_actions import EmailActionItemsFeature
from assistant.features.linkedin_feed import LinkedInFeedFeature
from assistant.integrations.base import GoogleAuthManager
from assistant.integrations.calendar import CalendarClient
from assistant.integrations.docs import DocsClient
from assistant.integrations.gmail import GmailClient
from assistant.integrations.linkedin import LinkedInDigestClient
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
    email_parser.add_argument(
        "--sms", action="store_true", help="Send output summary via SMS after printing."
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
    prep_parser.add_argument(
        "--sms", action="store_true", help="Send output summary via SMS after printing."
    )

    # -- linkedin subcommand --
    linkedin_parser = subparsers.add_parser("linkedin", help="Summarize LinkedIn network activity from digest emails.")
    linkedin_parser.add_argument(
        "--days", type=int, default=14, metavar="N",
        help="Number of days of digest emails to look back (default: 14)",
    )
    linkedin_parser.add_argument(
        "--sms", action="store_true", help="Send output summary via SMS after printing."
    )

    # -- daily subcommand --
    daily_parser = subparsers.add_parser(
        "daily", help="Generate a daily briefing and save it to Google Docs."
    )
    daily_parser.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Date to generate briefing for (default: today)",
    )
    daily_parser.add_argument(
        "--sms", action="store_true", help="Send output summary via SMS after printing."
    )

    # -- sms subcommand --
    sms_parser = subparsers.add_parser("sms", help="Run a command and send the output via SMS.")
    sms_sub = sms_parser.add_subparsers(dest="sms_command", required=True)

    sms_email_parser = sms_sub.add_parser("email", help="Send email action items via SMS.")
    sms_email_parser.add_argument(
        "--max-emails", type=int, default=20, metavar="N",
        help="Number of recent emails to analyze (default: 20)",
    )

    sms_cal_parser = sms_sub.add_parser("calendar", help="Send calendar prep via SMS.")
    sms_cal_sub = sms_cal_parser.add_subparsers(dest="sms_cal_command", required=True)
    sms_prep_parser = sms_cal_sub.add_parser("prep", help="Send prep notes for an event via SMS.")
    sms_prep_parser.add_argument("event_id", help="Google Calendar event ID")

    sms_linkedin_parser = sms_sub.add_parser("linkedin", help="Send LinkedIn summary via SMS.")
    sms_linkedin_parser.add_argument(
        "--days", type=int, default=14, metavar="N",
        help="Number of days of digest emails to look back (default: 14)",
    )

    sms_daily_parser = sms_sub.add_parser("daily", help="Generate daily briefing and notify via SMS.")
    sms_daily_parser.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Date to generate briefing for (default: today)",
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


def _send_sms(content: str, claude_client: ClaudeClient) -> None:
    """Summarize content with Claude and send to RECIPIENT_PHONE_NUMBER via SMS."""
    phone = os.getenv("RECIPIENT_PHONE_NUMBER")
    if not phone:
        raise ConfigurationError(
            "RECIPIENT_PHONE_NUMBER is not set. Add it to your .env file."
        )
    sms_feature = SmsSendFeature(claude_client, SmsClient())
    list(sms_feature.run(content, phone))
    print("✅ SMS sent.")


def main() -> None:
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set. Add it to your .env file.", file=sys.stderr)
        sys.exit(1)

    parser = _build_parser()
    args = parser.parse_args()

    try:
        auth_manager, gmail_client, calendar_client, claude_client = _build_clients(api_key, args.model)

        if args.command == "email":
            feature = EmailActionItemsFeature(gmail_client, claude_client)
            print(f"\n📬 Analyzing your {args.max_emails} most recent emails...\n")
            print("=" * 60)
            chunks = list(feature.run(max_emails=args.max_emails))
            for chunk in chunks:
                print(chunk, end="", flush=True)
            print("\n" + "=" * 60)
            if args.sms:
                _send_sms("".join(chunks), claude_client)

        elif args.command == "calendar":
            if args.cal_command == "list":
                feature = CalendarPrepFeature(calendar_client, claude_client)
                events = feature.list_upcoming(max_results=args.max_events)
                print(f"\n📅 Upcoming events ({len(events)} shown):\n")
                print(format_event_list(events))
                print("\nRun `assistant calendar prep <event-id>` to prepare for an event.")

            elif args.cal_command == "prep":
                feature = CalendarPrepFeature(calendar_client, claude_client)
                event = calendar_client.get_event_by_id(args.event_id)
                print(f"\n📅 Preparing for:\n")
                print(format_event_detail(event))
                print("\n" + "=" * 60)
                chunks = list(feature.run(args.event_id))
                for chunk in chunks:
                    print(chunk, end="", flush=True)
                print("\n" + "=" * 60)
                if args.sms:
                    _send_sms("".join(chunks), claude_client)

        elif args.command == "linkedin":
            linkedin_client = LinkedInDigestClient(gmail_client)
            feature = LinkedInFeedFeature(linkedin_client, claude_client)
            print(f"\n💼 LinkedIn network activity (last {args.days} days)...\n")
            print("=" * 60)
            chunks = list(feature.run(days=args.days))
            for chunk in chunks:
                print(chunk, end="", flush=True)
            print("\n" + "=" * 60)
            if args.sms:
                _send_sms("".join(chunks), claude_client)

        elif args.command == "daily":
            target_date = Date.fromisoformat(args.date) if args.date else Date.today()
            doc_id = os.getenv("DAILY_BRIEFING_DOC_ID") or None
            date_str = target_date.strftime("%A, %B %-d, %Y")

            docs_client = DocsClient(auth_manager)
            feature = DailyBriefingFeature(gmail_client, calendar_client, claude_client, docs_client)

            print(f"\n📋 Generating daily briefing for {date_str}...")
            print("=" * 60)

            returned_doc_id, doc_url = feature.run(target_date, doc_id)

            if doc_id is None:
                env_path = _PROJECT_ROOT / ".env"
                with open(env_path, "a") as f:
                    f.write(f"DAILY_BRIEFING_DOC_ID={returned_doc_id}\n")
                print("\n✅ Created new Google Doc and saved ID to .env")

            print(f"\n✅ Briefing written to: {doc_url}")
            print("=" * 60)
            if args.sms:
                _send_sms(f"Daily briefing for {date_str} is ready: {doc_url}", claude_client)

        elif args.command == "sms":
            phone = os.getenv("RECIPIENT_PHONE_NUMBER")
            if not phone:
                raise ConfigurationError(
                    "RECIPIENT_PHONE_NUMBER is not set. Add it to your .env file."
                )

            if args.sms_command == "email":
                feature = EmailActionItemsFeature(gmail_client, claude_client)
                content = "".join(feature.run(max_emails=args.max_emails))

            elif args.sms_command == "calendar":
                feature = CalendarPrepFeature(calendar_client, claude_client)
                content = "".join(feature.run(args.event_id))

            elif args.sms_command == "linkedin":
                linkedin_client = LinkedInDigestClient(gmail_client)
                feature = LinkedInFeedFeature(linkedin_client, claude_client)
                content = "".join(feature.run(days=args.days))

            elif args.sms_command == "daily":
                target_date = Date.fromisoformat(args.date) if args.date else Date.today()
                doc_id = os.getenv("DAILY_BRIEFING_DOC_ID") or None
                date_str = target_date.strftime("%A, %B %-d, %Y")
                docs_client = DocsClient(auth_manager)
                feature = DailyBriefingFeature(gmail_client, calendar_client, claude_client, docs_client)
                returned_doc_id, doc_url = feature.run(target_date, doc_id)
                if doc_id is None:
                    env_path = _PROJECT_ROOT / ".env"
                    with open(env_path, "a") as f:
                        f.write(f"DAILY_BRIEFING_DOC_ID={returned_doc_id}\n")
                content = f"Daily briefing for {date_str} is ready: {doc_url}"

            sms_feature = SmsSendFeature(claude_client, SmsClient())
            list(sms_feature.run(content, phone))
            print("✅ SMS sent.")

    except AssistantError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(0)

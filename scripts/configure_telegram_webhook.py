"""Configure or inspect the Medihub Telegram Bot API webhook."""

import argparse
import json
import os
import re
import sys

import httpx
from dotenv import load_dotenv


COMMANDS = [
    {"command": "start", "description": "Open the patient assistant"},
    {"command": "help", "description": "Show commands and safety guidance"},
    {"command": "register", "description": "Register a new patient"},
    {"command": "link", "description": "Link an existing patient account"},
    {"command": "hospitals", "description": "List available hospitals"},
    {"command": "doctors", "description": "List available doctors"},
    {"command": "speciality", "description": "Find a doctor by specialization"},
    {"command": "book", "description": "Book an appointment"},
    {"command": "facilities", "description": "View hospital facilities and services"},
    {"command": "appointments", "description": "View your appointments"},
    {"command": "prescriptions", "description": "View your prescriptions"},
    {"command": "reset", "description": "Reset the current conversation"},
]
SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def main() -> int:
    """Call Telegram configuration methods without printing secret credentials."""
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("set", "delete", "info"))
    parser.add_argument("--url", default=os.getenv("TELEGRAM_PUBLIC_WEBHOOK_URL", ""))
    args = parser.parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if not token:
        print("TELEGRAM_BOT_TOKEN is required.", file=sys.stderr)
        return 2
    api = f"{os.getenv('TELEGRAM_API_BASE_URL', 'https://api.telegram.org').rstrip('/')}/bot{token}"

    with httpx.Client(timeout=30) as client:
        if args.action == "set":
            if not args.url.startswith("https://"):
                print("An HTTPS --url is required.", file=sys.stderr)
                return 2
            if not SECRET_PATTERN.fullmatch(secret):
                print(
                    "TELEGRAM_WEBHOOK_SECRET must be 1-256 characters using only letters, numbers, _ or -.",
                    file=sys.stderr,
                )
                return 2
            response = client.post(
                f"{api}/setWebhook",
                json={
                    "url": args.url,
                    "secret_token": secret,
                    "allowed_updates": ["message", "callback_query"],
                    "drop_pending_updates": False,
                    # One connection preserves workflow order with the current
                    # process-local per-patient session lock.
                    "max_connections": 1,
                },
            )
            response.raise_for_status()
            commands = client.post(f"{api}/setMyCommands", json={"commands": COMMANDS})
            commands.raise_for_status()
            payload = response.json()
        elif args.action == "delete":
            response = client.post(
                f"{api}/deleteWebhook", json={"drop_pending_updates": False}
            )
            response.raise_for_status()
            payload = response.json()
        else:
            response = client.get(f"{api}/getWebhookInfo")
            response.raise_for_status()
            payload = response.json()

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

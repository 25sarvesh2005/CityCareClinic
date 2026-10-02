"""
scripts/migrate_db.py - Non-destructive schema migration for doctor profiles.

Usage:
    python scripts/migrate_db.py [--mongo-url <url>] [--db-name <name>]
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure backend directory and project root are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.config import get_db_name, get_mongo_url, load_project_env
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

load_project_env()


async def run_migration(mongo_url: str, db_name: str) -> int:
    client = None
    try:
        print(f"[Migration] Connecting to MongoDB: {db_name}...")
        client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        # Verify connection
        await client.admin.command("ping")
        print("[Migration] Database connection verified successfully.")

        db = client[db_name]
        result = await db["doctor_profiles"].update_many(
            {"unavailable_dates": {"$exists": False}},
            {"$set": {"unavailable_dates": []}},
        )
        print(
            f"[Migration Success] Database '{db_name}' updated. "
            f"Modified {result.modified_count} existing doctor profiles."
        )
        return 0
    except (PyMongoError, OSError, TimeoutError) as exc:
        print(
            f"[Migration Error] Could not connect or migrate database '{db_name}': "
            f"{exc.__class__.__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        if client is not None:
            client.close()


def main():
    parser = argparse.ArgumentParser(description="Run non-destructive schema migration for doctor profiles")
    parser.add_argument(
        "--mongo-url",
        default=get_mongo_url(),
        help="MongoDB connection URL (defaults to MONGO_URL from environment)",
    )
    parser.add_argument(
        "--db-name",
        default=get_db_name(),
        help="Database name (defaults to DB_NAME from environment)",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(run_migration(mongo_url=args.mongo_url, db_name=args.db_name))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

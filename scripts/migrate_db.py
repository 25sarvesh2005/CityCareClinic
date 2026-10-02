"""
scripts/migrate_db.py - Non-destructive schema migration for doctor profiles.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from motor.motor_asyncio import AsyncIOMotorClient
from common.config import get_db_name, get_mongo_url


async def run_migration():
    mongo_url = get_mongo_url()
    db_name = get_db_name()
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    result = await db["doctor_profiles"].update_many(
        {"unavailable_dates": {"$exists": False}},
        {"$set": {"unavailable_dates": []}}
    )
    print(f"Migration completed on {db_name}. Modified {result.modified_count} existing doctor profiles.")
    client.close()


if __name__ == "__main__":
    asyncio.run(run_migration())

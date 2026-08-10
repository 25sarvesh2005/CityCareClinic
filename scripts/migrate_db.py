import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def run_migration():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["citycare_clinic"]
    result = await db["doctor_profiles"].update_many(
        {"unavailable_dates": {"$exists": False}},
        {"$set": {"unavailable_dates": []}}
    )
    print(f"Migration completed. Modified {result.modified_count} existing doctor profiles.")

if __name__ == "__main__":
    asyncio.run(run_migration())

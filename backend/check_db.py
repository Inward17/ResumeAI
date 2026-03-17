import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check():
    db = AsyncIOMotorClient('mongodb://localhost:27017')['resumeai']
    tasks = await db.tasks.find().sort('created_at', -1).limit(3).to_list(length=3)
    for t in tasks:
        print(f"[{t.get('created_at')}] Task: {t.get('task_id')} | Status: {t.get('status')} | Error: {t.get('error')}")

if __name__ == "__main__":
    asyncio.run(check())

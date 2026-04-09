import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "resume_validator")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

agent_runs_col = db["agent_runs"]        # NEW: agent observability log
verification_data_agent_col = db["verification_data_agent"]  # Shadow collection (dual-run)
async def get_db():
    """FastAPI dependency to get database"""
    return db
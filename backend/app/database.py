import os
import logging

import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Local default for development. For a hosted database (MongoDB Atlas, etc.)
# set MONGO_URL to the provider's connection string, e.g.
#   mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "resume_validator")


def _client_options(url: str) -> dict:
    """Connection options that work for both local and hosted MongoDB."""
    options = {
        "maxPoolSize": int(os.getenv("MONGO_MAX_POOL_SIZE", "50")),
        "minPoolSize": int(os.getenv("MONGO_MIN_POOL_SIZE", "0")),
        "serverSelectionTimeoutMS": int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "10000")),
        "connectTimeoutMS": int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "10000")),
        "retryWrites": True,
        "appname": "resumeai-backend",
    }
    lowered = url.lower()
    # Hosted clusters use TLS; ship a CA bundle so it works on machines
    # without system certificates (Docker slim images, Windows, macOS python.org builds).
    if lowered.startswith("mongodb+srv://") or "tls=true" in lowered or "ssl=true" in lowered:
        options["tlsCAFile"] = certifi.where()
    return options


client = AsyncIOMotorClient(MONGO_URL, **_client_options(MONGO_URL))
db = client[DB_NAME]


async def get_db():
    """FastAPI dependency to get database"""
    return db


async def ping_database() -> bool:
    """Check connectivity at startup so a bad MONGO_URL is reported immediately."""
    try:
        await client.admin.command("ping")
        logger.info("Connected to MongoDB database '%s'", DB_NAME)
        return True
    except PyMongoError as exc:
        logger.error("Could not connect to MongoDB (%s): %s", _redacted_url(MONGO_URL), exc)
        return False


def _redacted_url(url: str) -> str:
    """Hide credentials when logging the connection string."""
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    return f"{scheme}://***@{rest.split('@', 1)[1]}"


# (collection, keys, options) — queries used on hot paths of the upload/verify pipeline.
_INDEXES = [
    ("tasks", [("task_id", ASCENDING)], {"unique": True}),
    ("tasks", [("status", ASCENDING), ("created_at", ASCENDING)], {}),
    ("tasks", [("job_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ("candidates", [("candidate_id", ASCENDING)], {"unique": True}),
    ("candidates", [("parsed.personal_info.full_name", ASCENDING), ("parsed.personal_info.phone_number", ASCENDING)], {}),
    ("applications", [("job_id", ASCENDING), ("candidate_id", ASCENDING)], {"unique": True}),
    ("applications", [("candidate_id", ASCENDING)], {}),
    ("verification_data", [("candidateId", ASCENDING)], {}),
    ("verification_data", [("candidate_id", ASCENDING)], {}),
    ("jobs", [("owner_uid", ASCENDING), ("posted_at", DESCENDING)], {}),
    ("users", [("uid", ASCENDING)], {"unique": True}),
]


async def ensure_indexes():
    """Create indexes idempotently. Failures (e.g. legacy duplicates) are logged, not fatal."""
    for collection, keys, options in _INDEXES:
        try:
            await db[collection].create_index(keys, **options)
        except PyMongoError as exc:
            logger.warning("Could not create index %s on %s: %s", keys, collection, exc)

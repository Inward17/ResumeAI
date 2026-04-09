import os
import asyncio
from apify_client import ApifyClient


APIFY_TOKEN = os.getenv("APIFY_TOKEN")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "yZnhB5JewWf9xSmoM")

client = ApifyClient(APIFY_TOKEN) if APIFY_TOKEN else None


def _scrape_sync(urls: list) -> dict:
    """Synchronous Apify scraping — runs inside a thread pool."""
    run_input = {
        "urls": [{"url": url} for url in urls],
        "scrapeCompany": False,
        "findContacts": False,
    }
    run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)
    dataset = client.dataset(run["defaultDatasetId"])
    results = list(dataset.iterate_items())
    return {"status": "success", "data": results}


async def scrape_linkedin_profiles(urls: list) -> dict:
    """Scrape LinkedIn profiles using Apify (non-blocking)"""
    if not client:
        raise Exception("Apify client not configured (missing APIFY_TOKEN)")
    
    try:
        return await asyncio.to_thread(_scrape_sync, urls)
    except Exception as e:
        raise Exception(f"Scraping failed: {str(e)}")
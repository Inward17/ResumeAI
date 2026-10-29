import os
import asyncio
from apify_client import ApifyClient


APIFY_TOKEN = os.getenv("APIFY_TOKEN")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "yZnhB5JewWf9xSmoM")

client = ApifyClient(APIFY_TOKEN) if APIFY_TOKEN else None


async def scrape_linkedin_profiles(urls: list) -> dict:
    """Scrape LinkedIn profiles using Apify"""
    if not client:
        raise Exception("Apify client not configured (missing APIFY_TOKEN)")
    
    try:
        run_input = {
            "urls": [{"url": url} for url in urls],
            "scrapeCompany": False,
            "findContacts": False,
        }
        
        # The Apify client is blocking and an actor run can take minutes;
        # run it in a thread so it doesn't freeze every other request/task.
        results = await asyncio.to_thread(_run_actor, run_input)
        
        return {"status": "success", "data": results}
    except Exception as e:
        raise Exception(f"Scraping failed: {str(e)}")


def _run_actor(run_input: dict) -> list:
    run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)
    dataset = client.dataset(run["defaultDatasetId"])
    return list(dataset.iterate_items())

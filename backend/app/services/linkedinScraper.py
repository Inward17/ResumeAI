import os
from apify_client import ApifyClient


APIFY_TOKEN = os.getenv("APIFY_TOKEN")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "yZnhB5JewWf9xSmoM")


def _get_client():
    """Create Apify client lazily to avoid import-time crashes."""
    if not APIFY_TOKEN:
        return None
    return ApifyClient(APIFY_TOKEN)


async def scrape_linkedin_profiles(urls: list) -> dict:
    """Scrape LinkedIn profiles using Apify"""
    client = _get_client()
    if not client:
        raise Exception("Apify client not configured (missing APIFY_TOKEN)")
    
    try:
        run_input = {
            "urls": [{"url": url} for url in urls],
            "scrapeCompany": False,
            "findContacts": False,
        }
        
        run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)
        dataset = client.dataset(run["defaultDatasetId"])
        results = list(dataset.iterate_items())
        
        return {"status": "success", "data": results}
    except Exception as e:
        raise Exception(f"Scraping failed: {str(e)}")

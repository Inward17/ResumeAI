from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from apify_client import ApifyClient
from dotenv import load_dotenv
import os
from ddgs import DDGS
import asyncio
from typing import Any, Dict, List, Union
from rapidfuzz import fuzz
import re # Import re for the search helper

# Load environment variables from .env
load_dotenv()

# Initialize FastAPI
app = FastAPI()

# Get APIFY token securely
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
if not APIFY_TOKEN:
    raise RuntimeError("Missing APIFY_TOKEN in .env file")

# Initialize the Apify client
client = ApifyClient(APIFY_TOKEN)

# Request body model
class LinkedInRequest(BaseModel):
    profileUrls: list[str]

@app.post("/scrape-linkedin")
def scrape_linkedin(data: LinkedInRequest):
    try:
        # --- MODIFIED SECTION ---
        # The actor 'yZnhB5JewWf9xSmoM' now expects a list of objects,
        # not just a list of strings. We format the input accordingly.
        formatted_urls = [{"url": url_str} for url_str in data.profileUrls]

        # Input for the Apify actor
        run_input = {
            "urls": formatted_urls,
            "scrapeCompany": False,
            "findContacts": False,
            "findContacts.contactCompassToken": "",
        }
        # --- END OF MODIFIED SECTION ---

        # Run the Apify actor
        # The actor ID is the same one you provided
        run = client.actor("yZnhB5JewWf9xSmoM").call(run_input=run_input)

        # Collect the scraped results
        results = [item for item in client.dataset(run["defaultDatasetId"]).iterate_items()]

        return {"status": "success", "data": results}

    except Exception as e:
        # Return a more specific error, potentially
        if "Cannot find actor" in str(e):
             raise HTTPException(status_code=404, detail=f"Actor 'yZnhB5JewWf9xSmoM' not found. Check ID.")
        if "Invalid input" in str(e):
            raise HTTPException(status_code=400, detail=f"Invalid input for actor: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Pydantic model ----------
class ProfileVerificationRequest(BaseModel):
    data: Union[Dict[str, Any], List[Dict[str, Any]]]


# ---------- Async Search Helper ----------
async def search_duckduckgo(query: str, field_type: str = None) -> Dict[str, Any]:
    try:
        def _search():
            with DDGS() as ddgs:
                search_query = query
                company_name = query # Default
                
                if field_type == "experience":
                    # Clean company name
                    company_name = re.sub(r'\s*·.*$', '', query)  # Remove "· Self-employed"
                    search_query = f"{company_name} official site OR website"
                elif field_type == "education":
                    search_query = f"{query} official site university"

                results = list(ddgs.text(search_query, max_results=5))
                if results:
                    for r in results:
                        # pick first result that mentions company_name
                        if field_type == "experience" and company_name.lower() in (r["title"].lower() + " " + r["href"].lower()):
                            return {
                                "verified": True,
                                "top_result": r["href"],
                                "title": r["title"],
                                "snippet": r["body"]
                            }
                        elif field_type == "education" and query.lower() in (r["title"].lower() + " " + r["href"].lower()):
                            return {
                                "verified": True,
                                "top_result": r["href"],
                                "title": r["title"],
                                "snippet": r["body"]
                            }
                    
                    # fallback: first result if no strong match
                    r = results[0]
                    return {
                        "verified": True,
                        "top_result": r["href"],
                        "title": r["title"],
                        "snippet": r["body"]
                    }
                return {"verified": False, "top_result": None}

        return await asyncio.to_thread(_search)

    except Exception as e:
        return {"verified": False, "error": str(e)}




# ---------- Parsing Logic ----------
def extract_entities(profile_json: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """Safely extract company and college names with roles."""
    educations = []
    experiences = []

    # Education parsing
    for edu in profile_json.get("educations", []):
        college = edu.get("title") or edu.get("subtitle") or "Unknown"
        if college and college != "Unknown":
            educations.append({"college": college})

    # Experience parsing
    for exp in profile_json.get("experiences", []):
        company = exp.get("subtitle") or exp.get("companyName") or exp.get("title")
        position = exp.get("title") or "Unknown"
        if company and company != "Unknown":
            experiences.append({"company": company, "position": position})

    return {"educations": educations, "experiences": experiences}


def compute_score_and_tag(entries: List[Dict[str, Any]], field_type: str) -> Dict[str, Any]:
    scored_entries = []
    total_score = 0

    if not entries:
        return {
            "details": [],
            "average_score": 0,
            "overall_tag": "Not Found"
        }

    for entry in entries:
        verified = entry.get("verified", False)
        snippet = entry.get("snippet", "") or ""
        title = entry.get("title", "") or ""
        position = entry.get("position", "").lower() if field_type == "experience" else ""

        combined_text = f"{title} {snippet}".lower()

        score = 0
        if not verified or entry.get("top_result") is None:
            score = 0
        elif field_type == "education":
            college_name = entry.get("college", "").lower()
            similarity = fuzz.token_set_ratio(college_name, combined_text)
            if similarity >= 90:
                score = 100
            elif similarity >= 70:
                score = 50
            else:
                score = 0
        elif field_type == "experience":
            company_name = entry.get("company", "").lower()
            # Clean company name for comparison
            company_name = re.sub(r'\s*·.*$', '', company_name)
            
            # Check if company exists in snippet/title
            company_similarity = fuzz.token_set_ratio(company_name, combined_text)
            
            if company_similarity >= 70:
                score = 50  # company found
                if position and position != "unknown" and position in combined_text:
                    score = 100  # position also confirmed
            else:
                score = 0

        # Tag logic
        if score >= 75:
            tag = "Verified"
        elif score <= 25:
            tag = "Not Found"
        else:
            tag = "Mismatch"

        total_score += score

        scored_entries.append({
            **entry,
            "score": score,
            "tag": tag
        })

    avg_score = round(total_score / len(scored_entries), 2) if scored_entries else 0

    return {
        "details": scored_entries,
        "average_score": avg_score,
        "overall_tag": (
            "Verified" if avg_score >= 75 else
            "Mismatch" if avg_score > 25 else
            "Not Found"
        )
    }



# ---------- Main Endpoint ----------
@app.post("/verify-profile-data")
async def verify_profile_data(req: ProfileVerificationRequest):
    try:
        # Handle single or multiple profiles
        profiles = req.data if isinstance(req.data, list) else [req.data]

        output = []
        for profile in profiles:
            extracted = extract_entities(profile)

            # Parallelize searches
            edu_tasks = [search_duckduckgo(e["college"], field_type="education") for e in extracted["educations"]]
            exp_tasks = [search_duckduckgo(e["company"], field_type="experience") for e in extracted["experiences"]]


            edu_results = await asyncio.gather(*edu_tasks)
            exp_results = await asyncio.gather(*exp_tasks)

            # Merge results
            verified_edu = [
                {**extracted["educations"][i], **edu_results[i]}
                for i in range(len(edu_results))
            ]
            verified_exp = [
                {**extracted["experiences"][i], **exp_results[i]}
                for i in range(len(exp_results))
            ]
            
            edu_score_info = compute_score_and_tag(verified_edu, field_type="education")
            exp_score_info = compute_score_and_tag(verified_exp, field_type="experience")

            output.append({
                "profile_url": profile.get("publicIdentifier") or profile.get("profileUrl") or "N/A", # Add some identifier
                "education": edu_score_info,
                "experience": exp_score_info
            })


        return {"status": "success", "results": output}

    except Exception as e:
        import traceback
        print(traceback.format_exc()) # Print full stack trace for debugging
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    import uvicorn
    # This block allows running directly for testing
    # uvicorn.run(app, host="0.0.0.0", port=8000)
    print("Run with: uvicorn main:app --reload")

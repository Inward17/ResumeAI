import re
import asyncio
from ddgs import DDGS


async def search_web(query: str, field_type: str = None) -> dict:
    """Search DuckDuckGo for verification"""
    return await asyncio.to_thread(_search_sync, query, field_type)


def _search_sync(query: str, field_type: str = None) -> dict:
    """Synchronous DuckDuckGo search"""
    try:
        with DDGS() as ddgs:
            search_query = query
            
            if field_type == "experience":
                company = re.sub(r'\s*·.*$', '', query)
                search_query = f"{company} official site OR website"
            elif field_type == "education":
                search_query = f"{query} official site university"
            
            results = list(ddgs.text(search_query, max_results=5))
            if not results:
                return {"verified": False, "top_result": None}
            
            # Return first result
            r = results[0]
            return {
                "verified": True,
                "top_result": r.get("href"),
                "title": r.get("title"),
                "snippet": r.get("body")
            }
    except Exception as e:
        return {"verified": False, "error": str(e)}
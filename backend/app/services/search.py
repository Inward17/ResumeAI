"""
Simple search service - ONLY handles web searching
No verification logic - that belongs in verifier.py
"""
import re
import asyncio
from typing import List, Dict
from ddgs import DDGS


async def search_web(query: str, field_type: str = None) -> List[Dict]:
    """
    Simple DuckDuckGo search - returns raw results
    
    Args:
        query: Search query
        field_type: 'education' or 'experience' (for query optimization)
    
    Returns:
        List of search results with href, title, body
    """
    return await asyncio.to_thread(_search_sync, query, field_type)


def _search_sync(query: str, field_type: str = None) -> List[Dict]:
    """Synchronous search implementation"""
    try:
        search_query = _optimize_query(query, field_type)
        
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=5))
            return results if results else []
    except Exception as e:
        return []


def _optimize_query(query: str, field_type: str = None) -> str:
    """Optimize search query based on field type"""
    if field_type in ("education", "university"):
        return f'"{query}" official website university'
    elif field_type in ("experience", "company"):
        company = re.sub(r'\s*·.*$', '', query)
        return f'"{company}" official website'
    return query
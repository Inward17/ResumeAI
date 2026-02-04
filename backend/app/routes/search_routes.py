from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.verifier import verify_entity  # Import from verifier, not search!

router = APIRouter(
    prefix="/api/v1/search",
    tags=["search"]
)

class SearchRequest(BaseModel):
    query: str
    field_type: Optional[str] = None

class SearchResult(BaseModel):
    verified: bool
    top_result: Optional[str] = None
    title: Optional[str] = None
    snippet: Optional[str] = None
    confidence: float = 0.0
    match_type: Optional[str] = None
    domain: Optional[str] = None
    matched_variation: bool = False
    error: Optional[str] = None

@router.post("/", response_model=SearchResult)
async def search_endpoint(request: SearchRequest):
    try:
        result = await verify_entity(request.query, request.field_type)
        return SearchResult(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
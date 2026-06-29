from fastapi import APIRouter

from api.ws_manager import get_review_traces

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/")
async def list_reviews():
    """List all code reviews."""
    return []


@router.get("/{review_id}")
async def get_review(review_id: str):
    """Get a specific code review by ID."""
    return {"id": review_id}


@router.get("/{review_id}/trace")
async def get_review_trace(review_id: str):
    """Return stored agent traces for a review."""
    return get_review_traces(review_id)

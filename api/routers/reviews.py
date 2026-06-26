from fastapi import APIRouter

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/")
async def list_reviews():
    """List all code reviews."""
    return []


@router.get("/{review_id}")
async def get_review(review_id: str):
    """Get a specific code review by ID."""
    return {"id": review_id}

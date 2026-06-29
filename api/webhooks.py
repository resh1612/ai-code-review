import hashlib
import hmac
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from models.review import Review

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


def _verify_signature(payload: bytes, signature_header: str) -> bool:
    """Return True if the HMAC-SHA256 signature matches the payload."""
    if not signature_header:
        return False

    secret = settings.GITHUB_WEBHOOK_SECRET.encode("utf-8")
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()

    if len(signature_header) != len(expected):
        return False

    return hmac.compare_digest(expected, signature_header)


@router.post("/webhook")
async def github_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Handle incoming GitHub App webhook events.

    - Verifies the HMAC-SHA256 signature; returns 403 on mismatch.
    - On pull_request opened/synchronize: creates a Review record and
      returns the new review ID.
    - All other events return {"status": "ignored"}.
    """
    payload = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(payload, signature_header):
        return JSONResponse(status_code=403, content={"error": "invalid signature"})

    event = request.headers.get("X-GitHub-Event", "")

    try:
        body: dict = json.loads(payload) if payload else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    action = body.get("action", "")

    if event == "pull_request" and action in {"opened", "synchronize"}:
        repo_name: str = body["repository"]["full_name"]
        pr_number: int = body["pull_request"]["number"]
        pr_diff_url: str = body["pull_request"]["diff_url"]

        logger.info(
            "PR event received: repo=%s pr=%s action=%s diff_url=%s",
            repo_name,
            pr_number,
            action,
            pr_diff_url,
        )

        review = Review(
            repo_name=repo_name,
            pr_number=pr_number,
            status="pending",
        )
        db.add(review)
        await db.flush()  # populates review.id before commit

        return {"status": "received", "review_id": str(review.id)}

    return {"status": "ignored"}

#Testing webhook
# webhook test
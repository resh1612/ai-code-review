"""Background review tasks with live WebSocket trace broadcasting."""

from __future__ import annotations

import asyncio
import logging

from agents.orchestrator import run_review
from api.ws_manager import schedule_trace_broadcast

logger = logging.getLogger(__name__)


async def process_review(
    review_id: str,
    pr_diff: str,
    repo_name: str,
    pr_number: int,
) -> None:
    """Run the review orchestrator and broadcast agent trace updates live."""
    loop = asyncio.get_running_loop()

    def trace_callback(trace_entry: dict) -> None:
        schedule_trace_broadcast(review_id, trace_entry, loop)

    logger.info("Starting review task %s for %s#%d", review_id, repo_name, pr_number)

    try:
        final_state = await run_review(
            pr_diff=pr_diff,
            repo_name=repo_name,
            pr_number=pr_number,
            trace_callback=trace_callback,
        )
        logger.info(
            "Review task %s completed with %d total findings",
            review_id,
            len(final_state.get("code_quality_findings", []))
            + len(final_state.get("security_findings", []))
            + len(final_state.get("test_findings", [])),
        )
    except Exception:
        logger.exception("Review task %s failed", review_id)
        raise

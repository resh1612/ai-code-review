"""In-memory WebSocket pub/sub for live agent trace updates."""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)

active_connections: dict[str, list[WebSocket]] = {}
review_traces: dict[str, list[dict]] = {}


def get_review_traces(review_id: str) -> list[dict]:
    return list(review_traces.get(review_id, []))


def _merge_trace(review_id: str, trace_entry: dict) -> None:
    traces = review_traces.setdefault(review_id, [])
    agent_name = trace_entry["agent_name"]

    for index, existing in enumerate(traces):
        if existing["agent_name"] == agent_name:
            traces[index] = {**existing, **trace_entry}
            return

    traces.append(trace_entry)


def disconnect_client(review_id: str, websocket: WebSocket) -> None:
    connections = active_connections.get(review_id, [])
    if websocket in connections:
        connections.remove(websocket)
    if review_id in active_connections and not active_connections[review_id]:
        del active_connections[review_id]


async def connect_client(review_id: str, websocket: WebSocket) -> None:
    await websocket.accept()
    active_connections.setdefault(review_id, []).append(websocket)
    await websocket.send_json(
        {
            "type": "snapshot",
            "traces": get_review_traces(review_id),
        }
    )


async def _send_to_clients(review_id: str, message: dict) -> None:
    connections = list(active_connections.get(review_id, []))
    dead: list[WebSocket] = []

    for websocket in connections:
        try:
            await websocket.send_json(message)
        except Exception:
            logger.warning("Removing disconnected WebSocket for review %s", review_id)
            dead.append(websocket)

    for websocket in dead:
        disconnect_client(review_id, websocket)


async def broadcast_trace_update(review_id: str, trace_entry: dict) -> None:
    """Send a trace update to all clients subscribed to *review_id*."""
    _merge_trace(review_id, trace_entry)
    await _send_to_clients(
        review_id,
        {
            "type": "update",
            "trace": trace_entry,
        },
    )


def schedule_trace_broadcast(
    review_id: str,
    trace_entry: dict,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Thread-safe broadcast helper for sync orchestrator callbacks."""
    _merge_trace(review_id, trace_entry)
    asyncio.run_coroutine_threadsafe(
        _send_to_clients(
            review_id,
            {
                "type": "update",
                "trace": trace_entry,
            },
        ),
        loop,
    )

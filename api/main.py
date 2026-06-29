from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.routers.reviews import router as reviews_router
from api.webhooks import router as webhooks_router
from api.ws_manager import (
    active_connections,
    broadcast_trace_update,
    connect_client,
    disconnect_client,
)

__all__ = ["active_connections", "broadcast_trace_update", "create_app", "app"]


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Code Review",
        description="AI-powered code review service",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(webhooks_router)
    app.include_router(reviews_router)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.websocket("/ws/review/{review_id}")
    async def review_trace_ws(websocket: WebSocket, review_id: str):
        await connect_client(review_id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            disconnect_client(review_id, websocket)

    return app


app = create_app()

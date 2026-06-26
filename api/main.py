from fastapi import FastAPI

from api.routers.reviews import router as reviews_router
from api.webhooks import router as webhooks_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Code Review",
        description="AI-powered code review service",
        version="0.1.0",
    )

    app.include_router(webhooks_router)
    app.include_router(reviews_router)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()

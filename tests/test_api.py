import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("GITHUB_APP_ID", "12345")
os.environ.setdefault("GITHUB_PRIVATE_KEY", "test-private-key")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")

from api.main import create_app
from core.database import get_db

WEBHOOK_SECRET = "test-webhook-secret"


def _pull_request_opened_payload() -> dict:
    return {
        "action": "opened",
        "repository": {
            "full_name": "owner/repo",
        },
        "pull_request": {
            "number": 1,
            "title": "Test PR",
            "diff_url": "https://github.com/owner/repo/pull/1.diff",
        },
    }


@pytest.fixture
def test_app(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
    from core.config import settings

    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)

    app = create_app()

    async def override_get_db():
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _sign_payload(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_webhook_invalid_signature_returns_403(client):
    body = _pull_request_opened_payload()
    payload = json.dumps(body).encode()
    wrong_signature = _sign_payload(payload, secret="wrong-secret")

    response = await client.post(
        "/webhook",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": wrong_signature,
            "X-GitHub-Event": "pull_request",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"error": "invalid signature"}


async def test_webhook_valid_pull_request_opened_returns_200(client):
    body = _pull_request_opened_payload()
    payload = json.dumps(body).encode()
    response = await client.post(
        "/webhook",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign_payload(payload),
            "X-GitHub-Event": "pull_request",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "review_id" in data

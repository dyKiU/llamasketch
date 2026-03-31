"""Integration tests for the FastAPI endpoints."""

import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["PENCIL_DEV_MODE"] = "true"
os.environ["PENCIL_USAGE_SALT"] = "test-salt"
os.environ["PENCIL_CORS_ORIGINS"] = "*"
os.environ["PENCIL_DAILY_FREE_LIMIT"] = "20"

_tmpdir = tempfile.mkdtemp()
os.environ["PENCIL_USAGE_DB"] = os.path.join(_tmpdir, "test_api.db")

from backend.main import app  # noqa: E402


@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health_dev_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/health")
    assert r.status_code == 200
    assert r.json()["comfyui_reachable"] is True


@pytest.mark.anyio
async def test_config_dev_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/config")
    data = r.json()
    assert data["dev_mode"] is True
    assert data["assist_enabled"] is True
    assert "daily_free_limit" in data


@pytest.mark.anyio
async def test_gpu_stats_dev_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/gpu")
    data = r.json()
    assert data["gpu_name"] == "Dev Mode (Mock GPU)"
    assert data["vram_total"] > 0


@pytest.mark.anyio
async def test_sketches():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/sketches")
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    ids = [s["id"] for s in data]
    assert "house" in ids
    assert "face" in ids


@pytest.mark.anyio
async def test_generate_and_usage():
    """Test generate + usage + daily limit in sequence with a fresh tracker."""
    from backend import main as m
    from backend.config import settings
    from backend.usage import UsageTracker

    db = os.path.join(_tmpdir, "test_gen.db")
    m.tracker = UsageTracker(db, "test-salt")
    settings.daily_free_limit = 3

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Usage starts at 0
        r = await c.get("/api/usage")
        assert r.json()["today"] == 0
        assert r.json()["remaining"] == 3

        # First generation succeeds
        r = await c.post("/api/generate", json={"sketch": "house"})
        assert r.status_code == 200
        assert r.json()["status"] == "queued"

        # Usage incremented
        r = await c.get("/api/usage")
        assert r.json()["today"] == 1
        assert r.json()["remaining"] == 2

        # Burn remaining quota
        await c.post("/api/generate", json={"sketch": "house"})
        await c.post("/api/generate", json={"sketch": "house"})

        # Fourth should be rejected
        r = await c.post("/api/generate", json={"sketch": "house"})
        assert r.status_code == 429
        assert "Daily limit" in r.json()["detail"]

        # Usage at limit
        r = await c.get("/api/usage")
        assert r.json()["remaining"] == 0

    settings.daily_free_limit = 20


@pytest.mark.anyio
async def test_assist_vision_dev_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/assist/vision", json={"image": "base64data"})
    assert r.status_code == 200
    data = r.json()
    assert data["subject"] == "sketch"


@pytest.mark.anyio
async def test_assist_prompt_dev_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/assist/prompt", json={"prompt": "a cat"})
    assert r.status_code == 200
    data = r.json()
    assert "a cat" in data["enhanced"]
    assert len(data["alternatives"]) == 2

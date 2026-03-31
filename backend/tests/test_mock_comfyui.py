"""Tests for MockComfyUIClient."""

import io

import pytest
from PIL import Image

from backend.mock_comfyui import MockComfyUIClient
from backend.models import JobStatus


@pytest.fixture()
def client():
    return MockComfyUIClient()


@pytest.mark.anyio
async def test_health_check(client):
    assert await client.health_check() is True


@pytest.mark.anyio
async def test_generate_returns_png(client):
    result = await client.generate(
        image_bytes=b"fake",
        prompt="test prompt",
        steps=4,
        denoise=0.75,
        seed=42,
    )
    assert isinstance(result, bytes)
    img = Image.open(io.BytesIO(result))
    assert img.size == (512, 512)
    assert img.mode == "RGB"


@pytest.mark.anyio
async def test_generate_hd(client):
    result = await client.generate(
        image_bytes=b"fake",
        prompt="hd test",
        steps=4,
        denoise=0.75,
        seed=42,
        hd=True,
    )
    img = Image.open(io.BytesIO(result))
    assert img.size == (1024, 1024)


@pytest.mark.anyio
async def test_generate_deterministic_seed(client):
    r1 = await client.generate(b"x", "p", 4, 0.75, seed=123)
    r2 = await client.generate(b"x", "p", 4, 0.75, seed=123)
    assert r1 == r2


@pytest.mark.anyio
async def test_on_status_callback(client):
    statuses = []
    await client.generate(
        b"x", "p", 4, 0.75, seed=1,
        on_status=lambda s: statuses.append(s),
    )
    assert JobStatus.uploading in statuses
    assert JobStatus.processing in statuses
    assert JobStatus.downloading in statuses


@pytest.mark.anyio
async def test_start_close_noop(client):
    await client.start()
    await client.close()

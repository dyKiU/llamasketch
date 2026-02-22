import asyncio
import base64
import collections
import io
import math
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw

from .comfyui import ComfyUIClient, ComfyUIError
from .config import settings
from .models import (
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    Job,
    JobStatus,
    JobStatusResponse,
    SketchInfo,
    UsageResponse,
)
from .usage import UsageTracker, get_client_ip, hash_ip

# ---------------------------------------------------------------------------
# Preset sketches (generated at import time)
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict] = {}


def _generate_house() -> Image.Image:
    img = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 250, 412, 450], outline="black", width=4)
    draw.polygon([(80, 250), (256, 80), (432, 250)], outline="black", width=4)
    draw.rectangle([220, 330, 292, 450], outline="black", width=3)
    draw.ellipse([270, 385, 282, 397], fill="black")
    draw.rectangle([130, 290, 195, 340], outline="black", width=3)
    draw.line([(162, 290), (162, 340)], fill="black", width=2)
    draw.line([(130, 315), (195, 315)], fill="black", width=2)
    draw.rectangle([317, 290, 382, 340], outline="black", width=3)
    draw.line([(349, 290), (349, 340)], fill="black", width=2)
    draw.line([(317, 315), (382, 315)], fill="black", width=2)
    return img


def _generate_face() -> Image.Image:
    img = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(img)
    draw.ellipse([80, 80, 432, 432], outline="black", width=4)
    draw.ellipse([170, 170, 210, 220], fill="black")
    draw.ellipse([302, 170, 342, 220], fill="black")
    draw.arc([160, 200, 352, 370], start=20, end=160, fill="black", width=4)
    return img


def _img_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _load_presets():
    from pathlib import Path

    # llama: real sketch file (default preset)
    llama_path = Path("static/img/llama-sketch.png")
    if llama_path.exists():
        PRESETS["llama"] = {
            "name": "Llama",
            "default_prompt": "a pencil sketch of a llama cartoon abstract logo",
            "image_bytes": llama_path.read_bytes(),
        }
    # birds: real sketch file
    birds_path = Path("static/img/input-sketch.png")
    if birds_path.exists():
        PRESETS["birds"] = {
            "name": "Birds",
            "default_prompt": "a colorful illustration of birds perched on branches, vibrant feathers, detailed nature scene",
            "image_bytes": birds_path.read_bytes(),
        }
    # house: generated
    PRESETS["house"] = {
        "name": "House",
        "default_prompt": "a colorful illustration of a cozy house with a red roof, green grass, blue sky, warm sunlight",
        "image_bytes": _img_to_png_bytes(_generate_house()),
    }
    # face: generated
    PRESETS["face"] = {
        "name": "Face",
        "default_prompt": "a colorful portrait illustration, warm skin tones, expressive eyes, soft lighting",
        "image_bytes": _img_to_png_bytes(_generate_face()),
    }


_load_presets()

# ---------------------------------------------------------------------------
# Job store
# ---------------------------------------------------------------------------

MAX_JOBS = 50
jobs: dict[str, Job] = {}

# Per-IP rate limiting: ip_hash -> deque of request timestamps
_rate_limits: dict[str, collections.deque] = {}


def _check_rate_limit(ip_hash: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = time.monotonic()
    window = settings.rate_limit_window
    max_req = settings.rate_limit_max

    if ip_hash not in _rate_limits:
        _rate_limits[ip_hash] = collections.deque()

    dq = _rate_limits[ip_hash]
    # Evict timestamps outside the window
    while dq and dq[0] <= now - window:
        dq.popleft()

    if len(dq) >= max_req:
        return False
    dq.append(now)
    return True


def _evict_old_jobs():
    """Remove oldest completed/failed jobs if store exceeds MAX_JOBS."""
    if len(jobs) <= MAX_JOBS:
        return
    terminal = [
        j for j in jobs.values()
        if j.status in (JobStatus.completed, JobStatus.failed, JobStatus.cancelled)
    ]
    terminal.sort(key=lambda j: j.created_at)
    while len(jobs) > MAX_JOBS and terminal:
        old = terminal.pop(0)
        jobs.pop(old.job_id, None)


# ---------------------------------------------------------------------------
# App lifecycle & client
# ---------------------------------------------------------------------------

client = ComfyUIClient()
tracker: UsageTracker


@asynccontextmanager
async def lifespan(app: FastAPI):
    global tracker
    tracker = UsageTracker(settings.usage_db, settings.usage_salt)
    await client.start()
    yield
    await client.close()


app = FastAPI(title="Pencil Flux Klein", lifespan=lifespan)

_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Background generation
# ---------------------------------------------------------------------------


async def _run_generation(job: Job, image_bytes: bytes, prompt: str, steps: int, denoise: float, hd: bool, seed: Optional[int]):
    try:
        png_bytes = await client.generate(
            image_bytes=image_bytes,
            prompt=prompt,
            steps=steps,
            denoise=denoise,
            seed=seed,
            hd=hd,
            on_status=lambda s: setattr(job, "status", s),
        )
        if job.status == JobStatus.cancelled:
            return
        job.result_image = png_bytes
        job.status = JobStatus.completed
    except (ComfyUIError, TimeoutError, httpx.ConnectError) as exc:
        job.error = str(exc)
        job.status = JobStatus.failed
    except Exception as exc:
        job.error = f"Unexpected error: {exc}"
        job.status = JobStatus.failed


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    return FileResponse("static/landing.html", media_type="text/html")


@app.get("/app")
async def app_page():
    return FileResponse("static/index.html", media_type="text/html")


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/api/config")
async def config():
    return {"signup_enabled": settings.signup_enabled, "git_commit": settings.git_commit}


@app.get("/api/health", response_model=HealthResponse)
async def health():
    try:
        reachable = await client.health_check()
        return HealthResponse(
            comfyui_reachable=reachable,
            comfyui_url=settings.comfyui_url,
        )
    except Exception as exc:
        return HealthResponse(
            comfyui_reachable=False,
            comfyui_url=settings.comfyui_url,
            error=str(exc),
        )


@app.get("/api/sketches", response_model=list[SketchInfo])
async def list_sketches():
    return [
        SketchInfo(id=k, name=v["name"], default_prompt=v["default_prompt"])
        for k, v in PRESETS.items()
    ]


@app.get("/api/sketches/{sketch_id}")
async def get_sketch(sketch_id: str):
    if sketch_id not in PRESETS:
        raise HTTPException(status_code=404, detail=f"Unknown sketch: {sketch_id}")
    return Response(
        content=PRESETS[sketch_id]["image_bytes"],
        media_type="image/png",
    )


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, request: Request):
    ip = get_client_ip(request)
    ip_hash = hash_ip(ip, settings.usage_salt)

    if not _check_rate_limit(ip_hash):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited: max {settings.rate_limit_max} requests per {settings.rate_limit_window}s",
        )

    tracker.record(ip_hash)

    # Resolve sketch image bytes
    if req.sketch in PRESETS:
        image_bytes = PRESETS[req.sketch]["image_bytes"]
        prompt = req.prompt or PRESETS[req.sketch]["default_prompt"]
    else:
        # Treat as base64-encoded image
        try:
            image_bytes = base64.b64decode(req.sketch)
        except Exception:
            raise HTTPException(status_code=400, detail="sketch must be a preset ID or valid base64")
        if len(image_bytes) > settings.max_image_size:
            raise HTTPException(status_code=400, detail=f"Image exceeds {settings.max_image_size} bytes")
        # Validate with Pillow and re-encode as PNG
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()
            # Re-open after verify (verify consumes the stream)
            img = Image.open(io.BytesIO(image_bytes))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image data")
        prompt = req.prompt or settings.default_prompt

    # Create job
    job_id = uuid.uuid4().hex
    job = Job(job_id)
    jobs[job_id] = job
    _evict_old_jobs()

    # Launch background generation
    asyncio.create_task(
        _run_generation(job, image_bytes, prompt, req.steps, req.denoise, req.hd, req.seed)
    )

    return GenerateResponse(job_id=job_id, status=job.status)


@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    job = jobs[job_id]
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        error=job.error,
        elapsed_seconds=round(time.time() - job.created_at, 2),
    )


@app.post("/api/cancel/{job_id}")
async def cancel_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    job = jobs[job_id]
    if job.status in (JobStatus.completed, JobStatus.failed, JobStatus.cancelled):
        return {"job_id": job_id, "status": job.status}
    job.status = JobStatus.cancelled
    job.result_image = None
    return {"job_id": job_id, "status": job.status}


@app.get("/api/gpu")
async def gpu_stats():
    """Proxy ComfyUI /system_stats for GPU/VRAM info and include job queue counts."""
    active_jobs = sum(
        1 for j in jobs.values()
        if j.status not in (JobStatus.completed, JobStatus.failed, JobStatus.cancelled)
    )
    try:
        resp = await client._client.get("/system_stats")
        data = resp.json()
        devices = data.get("devices", [])
        gpu = devices[0] if devices else {}
        return {
            "gpu_name": gpu.get("name", "Unknown"),
            "vram_total": gpu.get("vram_total", 0),
            "vram_free": gpu.get("vram_free", 0),
            "torch_vram_total": gpu.get("torch_vram_total", 0),
            "torch_vram_free": gpu.get("torch_vram_free", 0),
            "active_jobs": active_jobs,
        }
    except Exception:
        return {
            "gpu_name": "Unavailable",
            "vram_total": 0,
            "vram_free": 0,
            "torch_vram_total": 0,
            "torch_vram_free": 0,
            "active_jobs": active_jobs,
        }


@app.get("/api/result/{job_id}")
async def job_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    job = jobs[job_id]
    if job.status != JobStatus.completed:
        raise HTTPException(
            status_code=409,
            detail=f"Job not completed (status: {job.status.value})",
        )
    return Response(content=job.result_image, media_type="image/png")


@app.get("/api/usage", response_model=UsageResponse)
async def usage(request: Request):
    ip = get_client_ip(request)
    ip_hash = hash_ip(ip, settings.usage_salt)
    return UsageResponse(
        today=tracker.get_today(ip_hash),
        total=tracker.get_total(ip_hash),
        global_today=tracker.get_global_today(),
        global_total=tracker.get_global_total(),
        unique_users_today=tracker.get_unique_today(),
    )


@app.get("/api/usage/stats")
async def usage_stats():
    return {
        "global_today": tracker.get_global_today(),
        "global_total": tracker.get_global_total(),
        "unique_users_today": tracker.get_unique_today(),
    }

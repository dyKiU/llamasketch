import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    uploading = "uploading"
    submitted = "submitted"
    processing = "processing"
    downloading = "downloading"
    completed = "completed"
    failed = "failed"


class GenerateRequest(BaseModel):
    sketch: str = Field(..., description="Preset ID (e.g. 'birds') or base64-encoded PNG")
    prompt: Optional[str] = None
    steps: int = Field(default=4, ge=1, le=50)
    denoise: float = Field(default=0.75, ge=0.0, le=1.0)
    seed: Optional[int] = None


class GenerateResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    error: Optional[str] = None
    elapsed_seconds: Optional[float] = None


class SketchInfo(BaseModel):
    id: str
    name: str
    default_prompt: str


class HealthResponse(BaseModel):
    comfyui_reachable: bool
    comfyui_url: str
    error: Optional[str] = None


class Job:
    """Mutable job state — not a Pydantic model so we can update in place."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = JobStatus.queued
        self.result_image: Optional[bytes] = None
        self.error: Optional[str] = None
        self.comfyui_prompt_id: Optional[str] = None
        self.created_at = time.time()

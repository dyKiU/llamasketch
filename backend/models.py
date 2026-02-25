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
    cancelled = "cancelled"


class GenerateRequest(BaseModel):
    sketch: str = Field(..., description="Preset ID (e.g. 'birds') or base64-encoded PNG")
    prompt: Optional[str] = None
    steps: int = Field(default=4, ge=1, le=50)
    denoise: float = Field(default=0.75, ge=0.0, le=1.0)
    hd: bool = Field(default=False, description="Two-pass HD: generate at 512 then refine at 1024")
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


class UsageResponse(BaseModel):
    today: int
    total: int
    daily_limit: int  # 0 = unlimited
    remaining: int  # generations remaining today (-1 = unlimited)
    global_today: int
    global_total: int
    unique_users_today: int


class VisionRequest(BaseModel):
    image: str = Field(..., description="Base64-encoded PNG sketch image")


class VisionResponse(BaseModel):
    subject: str
    suggested_prompt: str
    composition_tips: list[str]


class PromptEnhanceRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)


class PromptEnhanceResponse(BaseModel):
    enhanced: str
    alternatives: list[str]


class Job:
    """Mutable job state — not a Pydantic model so we can update in place."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = JobStatus.queued
        self.result_image: Optional[bytes] = None
        self.error: Optional[str] = None
        self.comfyui_prompt_id: Optional[str] = None
        self.created_at = time.time()

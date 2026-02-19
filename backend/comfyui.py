import asyncio
import copy
import json
import random
import urllib.parse
from pathlib import Path
from typing import Callable, Optional

import httpx

from .config import settings


class ComfyUIError(Exception):
    pass


class ComfyUIClient:
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._workflow_template: Optional[dict] = None

    async def start(self):
        self._client = httpx.AsyncClient(
            base_url=settings.comfyui_url,
            timeout=settings.comfyui_timeout,
        )
        # Load workflow template
        path = Path(settings.workflow_template)
        if not path.exists():
            raise FileNotFoundError(f"Workflow template not found: {path}")
        self._workflow_template = json.loads(path.read_text())

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/")
            return resp.status_code == 200
        except httpx.ConnectError:
            return False

    async def upload_image(self, image_bytes: bytes, filename: str) -> str:
        """Upload image bytes to ComfyUI, return the server-side filename."""
        resp = await self._client.post(
            "/upload/image",
            files={"image": (filename, image_bytes, "image/png")},
            data={"overwrite": "true"},
        )
        resp.raise_for_status()
        result = resp.json()
        if "name" not in result:
            raise ComfyUIError(f"Upload response missing 'name': {result}")
        return result["name"]

    def build_workflow(
        self, image_filename: str, prompt: str, steps: int, seed: Optional[int]
    ) -> dict:
        """Build a workflow dict from template, injecting parameters."""
        wf = copy.deepcopy(self._workflow_template)
        # Node 1: LoadImage
        wf["1"]["inputs"]["image"] = image_filename
        # Node 6: Positive prompt
        wf["6"]["inputs"]["text"] = prompt
        # Node 8: RandomNoise seed (always set to avoid ComfyUI caching)
        wf["8"]["inputs"]["noise_seed"] = seed if seed is not None else random.randint(0, 2**53)
        # Node 10: Flux2Scheduler steps
        wf["10"]["inputs"]["steps"] = steps
        # Node 14: SaveImage prefix
        wf["14"]["inputs"]["filename_prefix"] = "pencil_flux"
        return wf

    async def submit_workflow(self, workflow: dict) -> str:
        """Submit workflow to ComfyUI, return prompt_id."""
        resp = await self._client.post(
            "/prompt",
            json={"prompt": workflow},
        )
        result = resp.json()
        if "error" in result:
            raise ComfyUIError(f"ComfyUI rejected workflow: {json.dumps(result, indent=2)}")
        if "prompt_id" not in result:
            raise ComfyUIError(f"Unexpected response from /prompt: {result}")
        return result["prompt_id"]

    async def poll_for_completion(self, prompt_id: str) -> dict:
        """Poll /history/{prompt_id} until done. Returns outputs dict."""
        deadline = asyncio.get_event_loop().time() + settings.comfyui_poll_timeout
        while asyncio.get_event_loop().time() < deadline:
            resp = await self._client.get(f"/history/{prompt_id}")
            history = resp.json()
            if prompt_id in history:
                entry = history[prompt_id]
                if entry.get("status", {}).get("status_str") == "error":
                    msgs = entry.get("status", {}).get("messages", [])
                    raise ComfyUIError(
                        f"ComfyUI workflow failed: {json.dumps(msgs, indent=2)}"
                    )
                outputs = entry.get("outputs", {})
                if outputs:
                    return outputs
            await asyncio.sleep(settings.comfyui_poll_interval)
        raise TimeoutError(
            f"Workflow {prompt_id} did not complete within {settings.comfyui_poll_timeout}s"
        )

    async def download_output_image(self, outputs: dict) -> bytes:
        """Download the output PNG from SaveImage node (node 14)."""
        save_node = outputs.get("14", {})
        images = save_node.get("images", [])
        if not images:
            raise ComfyUIError(f"No output images in node 14. Outputs: {outputs}")
        img_info = images[0]
        params = urllib.parse.urlencode({
            "filename": img_info["filename"],
            "subfolder": img_info.get("subfolder", ""),
            "type": img_info.get("type", "output"),
        })
        resp = await self._client.get(f"/view?{params}")
        resp.raise_for_status()
        return resp.content

    async def generate(
        self,
        image_bytes: bytes,
        prompt: str,
        steps: int,
        seed: Optional[int],
        on_status: Optional[Callable] = None,
    ) -> bytes:
        """Full pipeline: upload -> build -> submit -> poll -> download. Returns PNG bytes."""

        def _set(status):
            if on_status:
                on_status(status)

        from .models import JobStatus

        _set(JobStatus.uploading)
        filename = await self.upload_image(image_bytes, "pencil_input.png")

        _set(JobStatus.submitted)
        workflow = self.build_workflow(filename, prompt, steps, seed)
        prompt_id = await self.submit_workflow(workflow)

        _set(JobStatus.processing)
        outputs = await self.poll_for_completion(prompt_id)

        _set(JobStatus.downloading)
        return await self.download_output_image(outputs)

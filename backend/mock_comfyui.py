import asyncio
import io
import random
import textwrap
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont

from .config import settings
from .models import JobStatus


class MockComfyUIClient:
    """Drop-in replacement for ComfyUIClient that generates synthetic images
    without requiring a GPU or ComfyUI instance."""

    async def start(self):
        pass

    async def close(self):
        pass

    async def health_check(self) -> bool:
        return True

    def _render_synthetic_image(
        self, prompt: str, width: int, height: int, seed: Optional[int]
    ) -> bytes:
        rng = random.Random(seed if seed is not None else random.randint(0, 2**32))

        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        # Gradient background with seeded colours
        r1, g1, b1 = rng.randint(40, 180), rng.randint(40, 180), rng.randint(40, 180)
        r2, g2, b2 = rng.randint(80, 240), rng.randint(80, 240), rng.randint(80, 240)
        for y in range(height):
            t = y / max(height - 1, 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Checkerboard overlay for visual texture
        sq = max(width, height) // 16
        for row in range(0, height, sq):
            for col in range(0, width, sq):
                if (row // sq + col // sq) % 2 == 0:
                    draw.rectangle(
                        [col, row, col + sq - 1, row + sq - 1],
                        fill=None,
                        outline=(255, 255, 255, 40),
                    )

        # DEV MODE badge
        badge_h = 28
        draw.rectangle([0, 0, width, badge_h], fill=(0, 0, 0))
        draw.text((8, 6), "DEV MODE", fill=(255, 200, 0))

        # Prompt text wrapped in the centre
        wrapped = textwrap.fill(prompt[:200], width=max(width // 8, 20))
        lines = wrapped.split("\n")
        line_h = 16
        total_h = len(lines) * line_h
        y_start = (height - total_h) // 2
        for i, line in enumerate(lines):
            draw.text((12, y_start + i * line_h), line, fill=(255, 255, 255))

        # Seed label at bottom
        draw.text((8, height - 20), f"seed: {seed}", fill=(200, 200, 200))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    async def generate(
        self,
        image_bytes: bytes,
        prompt: str,
        steps: int,
        denoise: float,
        seed: Optional[int],
        hd: bool = False,
        on_status: Optional[Callable] = None,
    ) -> bytes:
        def _set(status: JobStatus):
            if on_status:
                on_status(status)

        _set(JobStatus.uploading)
        await asyncio.sleep(settings.dev_mode_delay * 0.1)

        _set(JobStatus.processing)
        await asyncio.sleep(settings.dev_mode_delay * 0.7)

        _set(JobStatus.downloading)
        await asyncio.sleep(settings.dev_mode_delay * 0.2)

        width, height = (1024, 1024) if hd else (512, 512)
        return self._render_synthetic_image(prompt, width, height, seed)

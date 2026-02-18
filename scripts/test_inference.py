#!/usr/bin/env python3
"""
FLUX Klein 4B Inference Test Suite

Self-contained test suite for verifying ComfyUI + FLUX Klein 4B inference
on a Vast.ai instance. Generates test sketch images with Pillow and validates
the full inference pipeline.

Usage:
    python3 test_inference.py [--comfyui-url http://127.0.0.1:8188] [--workflow workflow_template.json]
"""

import argparse
import io
import json
import math
import os
import sys
import time
import unittest
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

# Globals set by CLI args
COMFYUI_URL = "http://127.0.0.1:8188"
WORKFLOW_PATH = "workflow_template.json"

# Model files expected on the filesystem
MODEL_FILES = {
    "/workspace/ComfyUI/models/diffusion_models/flux-2-klein-4b-fp8.safetensors": 3_000_000_000,
    "/workspace/ComfyUI/models/text_encoders/qwen_3_4b.safetensors": 7_000_000_000,
    "/workspace/ComfyUI/models/vae/flux2-vae.safetensors": 300_000_000,
}

# Required ComfyUI node types for our workflow
REQUIRED_NODES = [
    "LoadImage",
    "VAELoader",
    "VAEEncode",
    "UNETLoader",
    "CLIPLoader",
    "CLIPTextEncode",
    "KSampler",
    "VAEDecode",
    "SaveImage",
]


# =============================================================================
# Test Sketch Generators (512x512, black lines on white)
# =============================================================================


def generate_circle_face() -> Image.Image:
    """Generate a simple smiley face: circle + eyes + smile."""
    img = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(img)
    # Head
    draw.ellipse([80, 80, 432, 432], outline="black", width=4)
    # Left eye
    draw.ellipse([170, 170, 210, 220], fill="black")
    # Right eye
    draw.ellipse([302, 170, 342, 220], fill="black")
    # Smile (arc)
    draw.arc([160, 200, 352, 370], start=20, end=160, fill="black", width=4)
    return img


def generate_house() -> Image.Image:
    """Generate a simple house: rectangle body + triangle roof + door + windows."""
    img = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(img)
    # House body
    draw.rectangle([100, 250, 412, 450], outline="black", width=4)
    # Roof (triangle)
    draw.polygon([(80, 250), (256, 80), (432, 250)], outline="black", width=4)
    # Door
    draw.rectangle([220, 330, 292, 450], outline="black", width=3)
    # Door knob
    draw.ellipse([270, 385, 282, 397], fill="black")
    # Left window
    draw.rectangle([130, 290, 195, 340], outline="black", width=3)
    draw.line([(162, 290), (162, 340)], fill="black", width=2)
    draw.line([(130, 315), (195, 315)], fill="black", width=2)
    # Right window
    draw.rectangle([317, 290, 382, 340], outline="black", width=3)
    draw.line([(349, 290), (349, 340)], fill="black", width=2)
    draw.line([(317, 315), (382, 315)], fill="black", width=2)
    return img


def generate_star() -> Image.Image:
    """Generate a five-pointed star."""
    img = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(img)
    cx, cy, r_outer, r_inner = 256, 256, 200, 80
    points = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, outline="black", width=4)
    return img


# =============================================================================
# Helper functions
# =============================================================================


def comfyui_request(path, method="GET", data=None, content_type=None):
    """Make an HTTP request to ComfyUI and return (status_code, response_body)."""
    url = f"{COMFYUI_URL}{path}"
    req = urllib.request.Request(url, method=method)
    if data is not None:
        if isinstance(data, str):
            data = data.encode("utf-8")
        req.data = data
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise ConnectionError(f"Cannot connect to ComfyUI at {COMFYUI_URL}: {e}")


def upload_image(img: Image.Image, filename: str) -> dict:
    """Upload a PIL Image to ComfyUI's /upload/image endpoint."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_data = buf.getvalue()

    # Build multipart form data manually
    boundary = "----PencilFluxTestBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8")
    body += image_data
    body += f"\r\n--{boundary}\r\n".encode("utf-8")
    body += (
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue'
    ).encode("utf-8")
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")

    url = f"{COMFYUI_URL}/upload/image"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def submit_workflow(workflow: dict) -> str:
    """Submit a workflow to ComfyUI and return the prompt_id."""
    payload = json.dumps({"prompt": workflow})
    status, body = comfyui_request(
        "/prompt", method="POST", data=payload, content_type="application/json"
    )
    result = json.loads(body)
    if "error" in result:
        error_msg = json.dumps(result, indent=2)
        raise RuntimeError(f"ComfyUI rejected workflow:\n{error_msg}")
    if "prompt_id" not in result:
        raise RuntimeError(f"Unexpected response from /prompt: {result}")
    return result["prompt_id"]


def poll_for_completion(prompt_id: str, timeout: float = 120.0) -> dict:
    """Poll /history/{prompt_id} until the job completes or times out."""
    start = time.time()
    while time.time() - start < timeout:
        status, body = comfyui_request(f"/history/{prompt_id}")
        history = json.loads(body)
        if prompt_id in history:
            entry = history[prompt_id]
            # Check for errors in the status
            if entry.get("status", {}).get("status_str") == "error":
                msgs = entry.get("status", {}).get("messages", [])
                raise RuntimeError(
                    f"ComfyUI workflow failed:\n{json.dumps(msgs, indent=2)}"
                )
            outputs = entry.get("outputs", {})
            if outputs:
                return outputs
        time.sleep(1.0)
    raise TimeoutError(f"Workflow {prompt_id} did not complete within {timeout}s")


def image_has_color(img: Image.Image, threshold: float = 0.05) -> bool:
    """Check if an image has significant non-grayscale pixels."""
    img_rgb = img.convert("RGB")
    pixels = list(img_rgb.getdata())
    colored = 0
    for r, g, b in pixels:
        # A pixel is "colored" if the channels differ significantly
        max_diff = max(abs(r - g), abs(r - b), abs(g - b))
        if max_diff > 20:
            colored += 1
    ratio = colored / len(pixels)
    return ratio > threshold


# =============================================================================
# Test Suite
# =============================================================================


class FluxKleinInferenceTests(unittest.TestCase):
    """Ordered test suite for verifying FLUX Klein 4B inference on ComfyUI."""

    def test_1_comfyui_alive(self):
        """GET / returns 200 — ComfyUI is running."""
        status, _ = comfyui_request("/")
        self.assertEqual(status, 200, f"ComfyUI returned status {status}, expected 200")

    def test_2_models_on_filesystem(self):
        """All 3 model files exist with correct minimum sizes."""
        for filepath, min_size in MODEL_FILES.items():
            with self.subTest(file=filepath):
                self.assertTrue(
                    os.path.isfile(filepath), f"Model file not found: {filepath}"
                )
                actual_size = os.path.getsize(filepath)
                self.assertGreaterEqual(
                    actual_size,
                    min_size,
                    f"{filepath}: {actual_size} bytes < expected minimum {min_size}",
                )

    def test_3_required_nodes_available(self):
        """/object_info has all required node types."""
        status, body = comfyui_request("/object_info")
        self.assertEqual(status, 200, "Failed to fetch /object_info")
        object_info = json.loads(body)
        for node_type in REQUIRED_NODES:
            with self.subTest(node=node_type):
                self.assertIn(
                    node_type,
                    object_info,
                    f"Required node type '{node_type}' not found in ComfyUI. "
                    f"Available nodes: {len(object_info)}",
                )

    def test_4_upload_image(self):
        """POST /upload/image succeeds with a test sketch."""
        img = generate_circle_face()
        result = upload_image(img, "test_circle_face.png")
        self.assertIn("name", result, f"Upload response missing 'name': {result}")
        print(f"\n  Uploaded image: {result.get('name')}")

    def test_5_full_inference(self):
        """Full round-trip: upload sketch -> run workflow -> download output -> validate colorized."""
        # Load workflow template
        workflow_file = Path(WORKFLOW_PATH)
        self.assertTrue(
            workflow_file.exists(), f"Workflow template not found: {WORKFLOW_PATH}"
        )
        workflow = json.loads(workflow_file.read_text())

        # Generate and upload test sketch
        sketch = generate_house()
        upload_result = upload_image(sketch, "test_house_sketch.png")
        uploaded_name = upload_result["name"]
        print(f"\n  Uploaded sketch: {uploaded_name}")

        # Configure workflow with our test parameters
        workflow["1"]["inputs"]["image"] = uploaded_name
        workflow["6"]["inputs"]["text"] = (
            "a colorful illustration of a cozy house with a red roof, "
            "green grass, blue sky, warm sunlight, vibrant colors"
        )
        workflow["8"]["inputs"]["seed"] = 12345
        workflow["8"]["inputs"]["denoise"] = 0.65

        # Submit workflow
        prompt_id = submit_workflow(workflow)
        print(f"  Submitted workflow, prompt_id: {prompt_id}")

        # Poll for completion
        outputs = poll_for_completion(prompt_id, timeout=120.0)
        print(f"  Workflow completed. Output nodes: {list(outputs.keys())}")

        # Find the SaveImage output (node "10")
        save_node = outputs.get("10", {})
        images = save_node.get("images", [])
        self.assertTrue(len(images) > 0, f"No output images found. Outputs: {outputs}")

        # Download the output image
        img_info = images[0]
        filename = img_info["filename"]
        subfolder = img_info.get("subfolder", "")
        img_type = img_info.get("type", "output")
        params = urllib.parse.urlencode(
            {"filename": filename, "subfolder": subfolder, "type": img_type}
        )
        status, img_data = comfyui_request(f"/view?{params}")
        self.assertEqual(status, 200, f"Failed to download output image: status {status}")

        # Validate it's a valid PNG
        output_img = Image.open(io.BytesIO(img_data))
        self.assertGreater(output_img.width, 0)
        self.assertGreater(output_img.height, 0)
        print(f"  Output image: {output_img.width}x{output_img.height}")

        # Validate it's colorized (not just black and white)
        has_color = image_has_color(output_img)
        self.assertTrue(
            has_color,
            "Output image appears to be grayscale — expected colorized output. "
            "The model may not be generating colored output at the current denoise level.",
        )
        print("  Output is colorized (has non-grayscale pixels).")

    def test_6_inference_timing(self):
        """Measures inference time. Warns if >5s, fails if >10s."""
        # Load workflow template
        workflow_file = Path(WORKFLOW_PATH)
        self.assertTrue(workflow_file.exists(), f"Workflow not found: {WORKFLOW_PATH}")
        workflow = json.loads(workflow_file.read_text())

        # Generate and upload a star sketch
        sketch = generate_star()
        upload_result = upload_image(sketch, "test_star_timing.png")
        workflow["1"]["inputs"]["image"] = upload_result["name"]
        workflow["6"]["inputs"]["text"] = (
            "a colorful five-pointed star, golden yellow, glowing, vibrant"
        )
        workflow["8"]["inputs"]["seed"] = 99999

        # Time the inference
        start = time.time()
        prompt_id = submit_workflow(workflow)
        poll_for_completion(prompt_id, timeout=30.0)
        elapsed = time.time() - start

        print(f"\n  Inference time: {elapsed:.2f}s")

        if elapsed > 5.0:
            print(f"  WARNING: Inference took {elapsed:.2f}s (>5s threshold)")

        self.assertLess(
            elapsed,
            10.0,
            f"Inference took {elapsed:.2f}s — exceeds 10s maximum. "
            "Check GPU utilization and model loading.",
        )


# =============================================================================
# CLI + Runner
# =============================================================================


def main():
    global COMFYUI_URL, WORKFLOW_PATH

    parser = argparse.ArgumentParser(
        description="Test FLUX Klein 4B inference on ComfyUI"
    )
    parser.add_argument(
        "--comfyui-url",
        default="http://127.0.0.1:8188",
        help="ComfyUI server URL (default: http://127.0.0.1:8188)",
    )
    parser.add_argument(
        "--workflow",
        default="workflow_template.json",
        help="Path to workflow template JSON (default: workflow_template.json)",
    )
    args, remaining = parser.parse_known_args()

    COMFYUI_URL = args.comfyui_url.rstrip("/")
    WORKFLOW_PATH = args.workflow

    print(f"ComfyUI URL: {COMFYUI_URL}")
    print(f"Workflow:    {WORKFLOW_PATH}")
    print("=" * 60)

    # Run tests in order with verbosity
    loader = unittest.TestLoader()
    loader.sortTestMethodsUsing = lambda a, b: (a > b) - (a < b)
    suite = loader.loadTestsFromTestCase(FluxKleinInferenceTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()

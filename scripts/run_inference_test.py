#!/usr/bin/env python3
"""Run inference tests against ComfyUI API.
Tests txt2img (EmptyLatentImage) and img2img (LoadImage + VAEEncode).
"""
import json
import sys
import time
import urllib.request
import urllib.error
import io
import struct
import zlib

COMFYUI_URL = "http://127.0.0.1:18188"


def make_png(width=512, height=512):
    """Generate a simple test PNG (circle face sketch) in memory."""
    # Create pixel data: white background with black circle and features
    pixels = []
    cx, cy, r = width // 2, height // 2, min(width, height) // 3
    for y in range(height):
        row = []
        for x in range(width):
            dx, dy = x - cx, y - cy
            dist = (dx * dx + dy * dy) ** 0.5
            # Circle outline
            if abs(dist - r) < 3:
                row.extend([0, 0, 0])
            # Left eye
            elif abs(x - cx + r // 3) < 8 and abs(y - cy + r // 4) < 8:
                row.extend([0, 0, 0])
            # Right eye
            elif abs(x - cx - r // 3) < 8 and abs(y - cy + r // 4) < 8:
                row.extend([0, 0, 0])
            # Smile (arc)
            elif (cy + r // 6 < y < cy + r // 3 and
                  abs(x - cx) < r // 2 and
                  abs(((x - cx) ** 2 + (y - cy - r // 6) ** 2) ** 0.5 - r // 2.5) < 3):
                row.extend([0, 0, 0])
            else:
                row.extend([255, 255, 255])
        pixels.append(bytes(row))

    # Encode as PNG
    def png_chunk(chunk_type, data):
        chunk = chunk_type + data
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

    raw = b""
    for row in pixels:
        raw += b"\x00" + row  # filter byte + row data

    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += png_chunk(b"IDAT", zlib.compress(raw))
    png += png_chunk(b"IEND", b"")
    return png


def api_post(path, data=None, files=None):
    """POST to ComfyUI API."""
    url = COMFYUI_URL + path
    if files:
        boundary = "----PythonBoundary"
        body = b""
        for key, (filename, content, content_type) in files.items():
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode()
            body += f"Content-Type: {content_type}\r\n\r\n".encode()
            body += content + b"\r\n"
        if data:
            for key, value in data.items():
                body += f"--{boundary}\r\n".encode()
                body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
                body += f"{value}\r\n".encode()
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, body, {
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        })
    else:
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, body, {"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def api_get(path, timeout=30):
    """GET from ComfyUI API."""
    url = COMFYUI_URL + path
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def submit_workflow(workflow):
    """Submit workflow and wait for completion."""
    prompt_data = {"prompt": workflow}
    try:
        result = api_post("/prompt", prompt_data)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ERROR submitting workflow: {e.code}")
        print(f"  {error_body[:2000]}")
        return None

    prompt_id = result.get("prompt_id")
    if not prompt_id:
        print(f"  ERROR: No prompt_id in response: {result}")
        return None

    print(f"  Submitted prompt_id: {prompt_id}")

    # Poll for completion
    start = time.time()
    timeout = 120  # 2 minutes max
    while time.time() - start < timeout:
        try:
            history_raw = api_get(f"/history/{prompt_id}")
            history = json.loads(history_raw)
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("completed", False) or status.get("status_str") == "success":
                    elapsed = time.time() - start
                    print(f"  Completed in {elapsed:.1f}s")
                    return entry
                if status.get("status_str") == "error":
                    print(f"  ERROR: Workflow failed")
                    msgs = status.get("messages", [])
                    for m in msgs:
                        print(f"    {m}")
                    return None
        except Exception:
            pass
        time.sleep(1)

    print(f"  TIMEOUT after {timeout}s")
    return None


def check_output_image(history_entry, expected_prefix):
    """Check if output image exists and is valid."""
    outputs = history_entry.get("outputs", {})
    for node_id, node_out in outputs.items():
        images = node_out.get("images", [])
        for img_info in images:
            filename = img_info.get("filename", "")
            subfolder = img_info.get("subfolder", "")
            img_type = img_info.get("type", "output")
            print(f"  Output image: {filename} (subfolder={subfolder}, type={img_type})")

            # Download and check
            params = f"filename={filename}&subfolder={subfolder}&type={img_type}"
            try:
                img_data = api_get(f"/view?{params}")
                print(f"  Image size: {len(img_data)} bytes")
                # Check it's a valid PNG
                if img_data[:4] == b"\x89PNG":
                    print(f"  Valid PNG: YES")
                    # Check dimensions from IHDR
                    w = struct.unpack(">I", img_data[16:20])[0]
                    h = struct.unpack(">I", img_data[20:24])[0]
                    print(f"  Dimensions: {w}x{h}")

                    # Check it's not all black or all white
                    # Simple check: look at pixel variance in IDAT
                    if len(img_data) < 1000:
                        print(f"  WARNING: Image suspiciously small ({len(img_data)} bytes)")
                    else:
                        print(f"  Image looks reasonable (size > 1KB)")
                    return True, img_data
                else:
                    print(f"  Not a valid PNG!")
                    return False, None
            except Exception as e:
                print(f"  Error downloading image: {e}")
                return False, None
    print(f"  No output images found!")
    return False, None


def test_txt2img():
    """Test text-to-image generation with EmptyLatentImage."""
    print("\n" + "=" * 60)
    print("TEST: txt2img (EmptyLatentImage)")
    print("=" * 60)

    workflow = {
        "1": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1}
        },
        "2": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "flux2-vae.safetensors"}
        },
        "4": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "flux-2-klein-4b.safetensors",
                "weight_dtype": "default"
            }
        },
        "5": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "flux2"}
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "a beautiful sunset over the ocean, vivid colors, detailed",
                "clip": ["5", 0]
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["5", 0]}
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["1", 0],
                "seed": 42,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0
            }
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["8", 0], "vae": ["2", 0]}
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {"images": ["9", 0], "filename_prefix": "txt2img_test"}
        }
    }

    result = submit_workflow(workflow)
    if result is None:
        print("  FAILED: Workflow did not complete")
        return False

    ok, img_data = check_output_image(result, "txt2img_test")
    if ok and img_data:
        # Save locally for inspection
        with open("/workspace/ComfyUI/output/txt2img_test_latest.png", "wb") as f:
            f.write(img_data)
        print("  PASSED")
        return True
    else:
        print("  FAILED: No valid output image")
        return False


def test_img2img():
    """Test image-to-image with a generated sketch."""
    print("\n" + "=" * 60)
    print("TEST: img2img (LoadImage + VAEEncode)")
    print("=" * 60)

    # Generate and upload test sketch
    png_data = make_png(512, 512)
    print(f"  Generated test sketch: {len(png_data)} bytes")

    try:
        result = api_post("/upload/image", files={
            "image": ("test_sketch.png", png_data, "image/png")
        }, data={"overwrite": "true"})
        print(f"  Upload result: {result}")
    except Exception as e:
        print(f"  Upload failed: {e}")
        return False

    workflow = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "test_sketch.png"}
        },
        "2": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "flux2-vae.safetensors"}
        },
        "3": {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["1", 0], "vae": ["2", 0]}
        },
        "4": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "flux-2-klein-4b.safetensors",
                "weight_dtype": "default"
            }
        },
        "5": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "flux2"}
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "a colorful illustration, vibrant colors, detailed shading",
                "clip": ["5", 0]
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["5", 0]}
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["3", 0],
                "seed": 42,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 0.65
            }
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["8", 0], "vae": ["2", 0]}
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {"images": ["9", 0], "filename_prefix": "img2img_test"}
        }
    }

    result = submit_workflow(workflow)
    if result is None:
        print("  FAILED: Workflow did not complete")
        return False

    ok, img_data = check_output_image(result, "img2img_test")
    if ok and img_data:
        with open("/workspace/ComfyUI/output/img2img_test_latest.png", "wb") as f:
            f.write(img_data)
        print("  PASSED")
        return True
    else:
        print("  FAILED: No valid output image")
        return False


if __name__ == "__main__":
    print("ComfyUI Inference Tests")
    print(f"URL: {COMFYUI_URL}")

    # Check alive
    try:
        api_get("/")
        print("ComfyUI is alive")
    except Exception as e:
        print(f"ComfyUI not reachable: {e}")
        sys.exit(1)

    results = {}

    # Run txt2img first (simpler, no VAE encode)
    results["txt2img"] = test_txt2img()

    # Run img2img
    results["img2img"] = test_img2img()

    print("\n" + "=" * 60)
    print("RESULTS:")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
    print("=" * 60)

    if all(results.values()):
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)

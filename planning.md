# Pencil Flux Klein - Project Planning

## Project Overview

**Pencil Flux Klein** is a single-user web application that autocompletes and colorizes pencil sketches using the FLUX.2 Klein 4B model. Users upload (or select from preloaded) pencil sketches, the app sends them to a Vast.ai-hosted ComfyUI instance running FLUX Klein 4B, and the AI returns a colorized/completed version displayed as an overlay on the original sketch.

### Goals

- Provide a simple, fast sketch-to-color workflow with ~1-2 second inference
- Zero authentication overhead (single user)
- Clean overlay UI comparing original sketch with AI output
- Support transparent PNG input/output for clean compositing
- Minimal infrastructure: one local webapp + one Vast.ai GPU instance

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER'S MACHINE                           │
│                                                                 │
│  ┌──────────────────────┐    ┌────────────────────────────────┐ │
│  │   Browser (Frontend)  │◄──►│    Backend Server (Python)     │ │
│  │                       │    │                                │ │
│  │  - Upload / select    │    │  - Serves frontend             │ │
│  │    sketch             │    │  - Proxies requests to Vast.ai │ │
│  │  - Overlay viewer     │    │  - Handles image upload/       │ │
│  │  - Prompt input       │    │    download                    │ │
│  │  - Denoise slider     │    │  - Manages workflow JSON       │ │
│  │                       │    │  - Reads config (preloaded     │ │
│  │                       │    │    sketches)                   │ │
│  └──────────────────────┘    └──────────┬─────────────────────┘ │
│                                         │                       │
└─────────────────────────────────────────┼───────────────────────┘
                                          │ HTTPS
                                          │ (Cloudflare tunnel or
                                          │  direct IP:port)
                                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VAST.AI GPU INSTANCE                          │
│                    (RTX 3090 / RTX 4090)                        │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    ComfyUI Server                          │ │
│  │                    (port 8188)                              │ │
│  │                                                            │ │
│  │  Models:                                                   │ │
│  │  ├── diffusion_models/flux-2-klein-4b-fp8.safetensors      │ │
│  │  ├── text_encoders/qwen_3_4b.safetensors                   │ │
│  │  └── vae/flux2-vae.safetensors                             │ │
│  │                                                            │ │
│  │  REST API:                                                 │ │
│  │  ├── POST /upload/image   (receive sketch)                 │ │
│  │  ├── POST /prompt         (submit workflow)                │ │
│  │  ├── GET  /history/{id}   (poll for results)               │ │
│  │  ├── GET  /view           (download generated image)       │ │
│  │  └── WS   /ws             (real-time progress)             │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Why proxy through the backend?

- Avoids CORS issues (browser cannot directly call Vast.ai ComfyUI)
- Keeps Vast.ai instance URL/credentials out of the frontend
- Backend can inject workflow JSON, manage retries, and transform responses
- Backend serves preloaded sketches from local config

---

## Tech Stack

### Frontend

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Framework | **Vanilla JS + HTML/CSS** or **Svelte** | Single-page, no auth, minimal complexity. Svelte if we want reactivity without heavy framework overhead. |
| Image overlay | HTML5 Canvas or CSS `mix-blend-mode` | Overlay AI output on original sketch with opacity slider |
| Upload | Native `<input type="file">` | Accept PNG files |
| HTTP client | `fetch` API | Standard, no dependencies |

### Backend

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | **Python 3.11+** | Matches ComfyUI ecosystem, good image handling |
| Framework | **FastAPI** | Async, fast, easy to build REST proxy |
| Image handling | **Pillow** | PNG transparency, compositing, resizing |
| WebSocket client | **websockets** | Monitor ComfyUI job progress |
| Config | **YAML** or **TOML** | Preloaded sketch definitions |
| HTTP client | **httpx** | Async HTTP to call ComfyUI API |

### Vast.ai Instance

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Template | **ComfyUI** (official Vast.ai template) | Pre-configured CUDA 12.4 + ComfyUI |
| GPU | **RTX 3090** (24 GB) or **RTX 4090** (24 GB) | Klein 4B FP8 needs ~8 GB VRAM; plenty of headroom |
| Model | **FLUX.2 Klein 4B Distilled (FP8)** | 4-step inference, ~1.2s generation, Apache 2.0 license |
| Networking | **Cloudflare tunnel** (dev) / **Static IP** (prod) | Cloudflare tunnel is automatic via Vast.ai Instance Portal |
| Storage | **50-100 GB** | ~10 GB for models + working space |

---

## API Design

### Backend Endpoints (FastAPI)

```
GET  /                          → Serve frontend (index.html)
GET  /api/health                → Health check + Vast.ai connection status
GET  /api/sketches              → List preloaded sketches from config
GET  /api/sketches/{id}/image   → Serve a preloaded sketch image file
POST /api/generate              → Submit sketch for colorization
GET  /api/generate/{job_id}     → Poll job status + get result
GET  /api/result/{job_id}/image → Download generated image (PNG)
```

### POST /api/generate - Request

```json
{
  "sketch_source": "upload" | "preloaded",
  "sketch_id": "cat_simple",          // if preloaded
  "sketch_file": "<base64 PNG>",      // if upload
  "prompt": "A colorful illustration of a cat, vibrant colors, detailed shading",
  "denoise": 0.65,                    // 0.0-1.0, default 0.65
  "seed": -1                          // -1 = random
}
```

### POST /api/generate - Response

```json
{
  "job_id": "abc-123-uuid",
  "status": "queued"
}
```

### GET /api/generate/{job_id} - Response

```json
{
  "job_id": "abc-123-uuid",
  "status": "queued" | "processing" | "completed" | "failed",
  "progress": 0.75,                   // 0.0-1.0 during processing
  "result_url": "/api/result/abc-123-uuid/image",  // when completed
  "error": null
}
```

---

## Data Flow

```
1. User selects/uploads sketch (PNG, transparent background)
         │
         ▼
2. Frontend sends POST /api/generate with sketch + prompt + denoise
         │
         ▼
3. Backend receives request
   ├── If upload: decode base64, validate PNG, save temporarily
   └── If preloaded: load from configured path
         │
         ▼
4. Backend uploads sketch to ComfyUI via POST /upload/image
         │
         ▼
5. Backend constructs workflow JSON:
   ├── LoadImage (uploaded sketch filename)
   ├── VAEEncode (sketch → latent space)
   ├── CLIPLoader (qwen_3_4b text encoder)
   ├── CLIPTextEncode (user prompt)
   ├── KSampler (denoise=user_value, steps=4, cfg=1.0, euler/simple)
   ├── VAEDecode (latent → pixels)
   └── SaveImage (output PNG)
         │
         ▼
6. Backend submits workflow via POST /prompt to ComfyUI
   └── Opens WebSocket to /ws for progress tracking
         │
         ▼
7. ComfyUI executes (FLUX Klein 4B, ~1-2 seconds)
         │
         ▼
8. Backend polls /history/{prompt_id} or receives WS completion
         │
         ▼
9. Backend downloads result via GET /view?filename=...&type=output
         │
         ▼
10. Backend stores result, returns to frontend
         │
         ▼
11. Frontend displays result as overlay on original sketch
    └── Opacity slider to blend between original and colorized
```

---

## Config File Structure

### `config.yaml`

```yaml
# Vast.ai ComfyUI connection
comfyui:
  url: "https://four-random-words.trycloudflare.com"  # or http://IP:PORT
  # Updated each time a new Vast.ai instance is started

# FLUX Klein 4B model settings
model:
  diffusion_model: "flux-2-klein-4b-fp8.safetensors"
  text_encoder: "qwen_3_4b.safetensors"
  vae: "flux2-vae.safetensors"

# Default generation parameters
defaults:
  denoise: 0.65
  steps: 4
  cfg: 1.0
  sampler: "euler"
  scheduler: "simple"
  width: 1024
  height: 1024

# Preloaded sketches
sketches:
  - id: "cat_simple"
    name: "Simple Cat"
    file: "sketches/cat_simple.png"
    default_prompt: "A colorful illustration of a cute cat, vibrant fur, soft lighting"

  - id: "landscape_hills"
    name: "Rolling Hills"
    file: "sketches/landscape_hills.png"
    default_prompt: "A beautiful landscape with rolling green hills, blue sky, warm sunlight"

  - id: "flower_bouquet"
    name: "Flower Bouquet"
    file: "sketches/flower_bouquet.png"
    default_prompt: "A vibrant bouquet of flowers, roses and daisies, rich colors, natural lighting"
```

### `workflow_template.json`

A ComfyUI API-format workflow JSON (exported from ComfyUI with Dev Mode enabled) stored alongside the config. The backend loads this template and injects dynamic values (uploaded filename, prompt text, denoise, seed) before submitting to ComfyUI.

---

## Vast.ai Setup Instructions

### 1. Account Setup

1. Create account at [vast.ai](https://vast.ai)
2. Add minimum $5 credit
3. Note: per-second billing, instances can be stopped when not in use

### 2. Rent a GPU Instance

1. Go to **Templates** → select **ComfyUI** template
2. On the search/rent page, filter:
   - GPU: RTX 3090 or RTX 4090
   - VRAM: >= 12 GB
   - Storage: set to **80 GB** (cannot change later)
   - Sort by price or reliability
   - Check "Internet $/TB" column (pick low egress cost for model downloads)
3. Click **RENT** on a suitable machine

### 3. Download FLUX Klein 4B Models

SSH into the instance or use the Jupyter terminal:

```bash
# Install huggingface_hub if needed
pip install huggingface_hub

# Download models
python -c "
from huggingface_hub import hf_hub_download

# Distilled diffusion model (FP8)
hf_hub_download(
    'black-forest-labs/FLUX.2-klein-4b-fp8',
    filename='flux-2-klein-4b-fp8.safetensors',
    local_dir='/workspace/ComfyUI/models/diffusion_models/'
)

# Text encoder
hf_hub_download(
    'black-forest-labs/FLUX.2-klein-4B',
    filename='qwen_3_4b.safetensors',
    local_dir='/workspace/ComfyUI/models/text_encoders/'
)

# VAE
hf_hub_download(
    'black-forest-labs/FLUX.2-klein-4B',
    filename='flux2-vae.safetensors',
    local_dir='/workspace/ComfyUI/models/vae/'
)
"
```

### 4. Verify ComfyUI Access

1. Click **Open** on the Vast.ai instance → Instance Portal
2. ComfyUI should be accessible on port 8188
3. Note the Cloudflare tunnel URL (e.g., `https://four-random-words.trycloudflare.com`)
4. Test: open the URL in a browser, verify ComfyUI UI loads
5. Update `config.yaml` with this URL

### 5. Create and Export the Workflow

1. In ComfyUI UI, build the img2img workflow (see ComfyUI Workflow section below)
2. Test it manually with a sample sketch
3. Enable **Dev Mode** in ComfyUI settings
4. Click **Save (API Format)** to export `workflow_api.json`
5. Copy this file to the local project as `workflow_template.json`

### 6. Cost Management

- **Stop** the instance when not in use (small daily storage fee, no compute charge)
- **Destroy** when done for the day (no charges, but lose local data — models must be re-downloaded)
- Typical cost: RTX 3090 at ~$0.20-0.40/hr, RTX 4090 at ~$0.30-0.50/hr

---

## ComfyUI Workflow Design

### Primary Approach: img2img with Denoise Control

This is the simplest approach and works well with FLUX Klein 4B:

```
LoadImage (sketch.png)
    │
    ▼
VAEEncode ──────────────────────────────────────┐
                                                │
CLIPLoader (qwen_3_4b) ──► CLIPTextEncode ──┐   │
                           (user prompt)    │   │
                                            ▼   ▼
                                         KSampler
                                         ├── steps: 4
                                         ├── cfg: 1.0
                                         ├── sampler: euler
                                         ├── scheduler: simple
                                         └── denoise: 0.65
                                            │
                                            ▼
UNETLoader ─────────────────────────────► (model input)
(flux-2-klein-4b-fp8)

VAELoader ──────────────────────────────► VAEDecode
(flux2-vae)                                 │
                                            ▼
                                        SaveImage
                                        (output PNG)
```

### Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| `denoise` | 0.50 - 0.75 | **Critical control**. Lower = preserves more sketch structure. Higher = more creative freedom. Start at 0.65. |
| `steps` | 4 | Fixed for distilled model. Do not change. |
| `cfg` | 1.0 | Fixed for distilled model. Must be exactly 1.0. |
| `sampler` | euler | Recommended for FLUX |
| `scheduler` | simple | Recommended for FLUX |
| `seed` | random or fixed | Fixed seed for reproducibility during testing |

### Denoise Guidelines for Sketch Colorization

| Denoise | Effect |
|---------|--------|
| 0.3-0.4 | Light color wash, preserves fine line detail |
| 0.5-0.6 | Moderate colorization, good balance |
| **0.6-0.7** | **Recommended starting range** — vibrant color with preserved composition |
| 0.7-0.8 | Bold reinterpretation, some detail loss |
| 0.9-1.0 | Near-complete regeneration, only vague hints of sketch |

### Alternative Approach: ControlNet (if img2img quality is insufficient)

If basic img2img does not preserve enough sketch structure, we can add ControlNet:

- Use **Flux MistoLine** ControlNet (designed for lineart/sketches, ~1.4B params)
- Or **FLUX.1-Canny-dev** ControlNet with Canny edge preprocessor
- Adds `LoadFluxControlNet` → `CannyEdgePreprocessor` → `ApplyFluxControlNet` nodes
- ControlNet strength 0.6-0.8 for sketch adherence
- Trade-off: requires downloading additional model (~3+ GB), slightly slower

**Decision: Start with img2img. Evaluate quality. Add ControlNet only if needed.**

### Transparent PNG Handling

- ComfyUI's `LoadImage` node separates PNG alpha channel into a `MASK` output
- For sketch input: the alpha channel can be used to identify drawn vs. empty areas
- For output: use `SaveImage` node (outputs standard RGB PNG)
- Overlay compositing is done in the frontend (original sketch PNG over AI output), not in ComfyUI
- If alpha-preserved output is needed: install `ComfyUI-KJNodes` for `SaveImageWithAlpha`

---

## MVP Milestones

### Milestone 1: Infrastructure Setup
- [ ] Rent Vast.ai instance with ComfyUI template
- [ ] Download FLUX Klein 4B models (diffusion, text encoder, VAE)
- [ ] Verify ComfyUI loads and runs via browser
- [ ] Build and test img2img workflow manually in ComfyUI UI
- [ ] Export workflow in API format
- [ ] Test API call from local machine using `curl` or Python script

### Milestone 2: Backend API
- [ ] Set up FastAPI project structure
- [ ] Implement config loading (YAML + workflow template)
- [ ] Implement ComfyUI proxy client (upload image, submit workflow, poll results, download output)
- [ ] Implement `/api/generate` endpoint (upload + preloaded sketch support)
- [ ] Implement `/api/generate/{job_id}` polling endpoint
- [ ] Implement `/api/sketches` endpoints for preloaded sketches
- [ ] Test full round-trip: backend → ComfyUI → backend

### Milestone 3: Frontend
- [ ] Build single-page HTML/JS/CSS interface
- [ ] Sketch selection UI (upload button + 3 preloaded thumbnails)
- [ ] Prompt input field (pre-filled with default prompt for preloaded sketches)
- [ ] Denoise slider (0.0-1.0 with sensible default)
- [ ] Generate button + loading state with progress indicator
- [ ] Result display: overlay viewer with opacity slider
- [ ] Side-by-side or toggle view of original vs. colorized

### Milestone 4: Polish & Integration
- [ ] Error handling (Vast.ai offline, generation failures, timeouts)
- [ ] Create 3 preloaded pencil sketch PNG files
- [ ] Tune default prompts and denoise values per sketch
- [ ] Input validation (PNG format, reasonable dimensions, file size limit)
- [ ] Basic responsive layout

---

## File Structure

```
pencil-flux-klein/
├── planning.md                      # This document
├── config.yaml                      # App configuration (ComfyUI URL, sketches, defaults)
├── workflow_template.json           # ComfyUI API-format workflow (exported from ComfyUI)
│
├── backend/
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # Config loader (reads config.yaml)
│   ├── comfyui_client.py            # ComfyUI API client (upload, prompt, poll, download)
│   ├── routes.py                    # API route handlers
│   ├── models.py                    # Pydantic request/response models
│   └── requirements.txt             # Python dependencies
│
├── frontend/
│   ├── index.html                   # Single-page app
│   ├── style.css                    # Styles
│   └── app.js                       # Frontend logic (upload, generate, overlay viewer)
│
├── sketches/                        # Preloaded pencil sketch PNGs
│   ├── cat_simple.png
│   ├── landscape_hills.png
│   └── flower_bouquet.png
│
└── scripts/
    └── setup_vastai.sh              # Helper script for Vast.ai model downloads
```

---

## Open Questions / Decisions Needed

### 1. FLUX Klein img2img vs. native image editing mode
- **img2img (VAEEncode → KSampler with denoise < 1.0):** Simpler workflow, well-understood, works with standard ComfyUI nodes. Denoise slider directly controls sketch preservation.
- **Klein native editing (ReferenceLatent nodes):** Uses Klein's built-in vision-language understanding for instruction-based editing. Potentially better semantic understanding of sketches. But newer, less documented, may require specific ComfyUI node versions.
- **Recommendation:** Start with img2img. It's proven and the denoise slider maps directly to user intent.

### 2. ControlNet: include from the start or defer?
- Adding ControlNet (e.g., MistoLine for lineart) would give better structure preservation but adds model download time, VRAM usage, and workflow complexity.
- **Recommendation:** Defer. Test img2img first. Add ControlNet as an enhancement if sketch structure is not well-preserved at useful denoise levels.

### 3. Frontend framework
- **Vanilla JS:** Zero build step, simplest possible setup. Fine for a single-page app.
- **Svelte:** Slightly nicer reactivity for the overlay/slider UI. Small build step.
- **Recommendation:** Start with vanilla JS. The UI is simple enough.

### 4. Vast.ai networking for production
- **Cloudflare tunnel:** Free, HTTPS, but URL changes each time instance restarts.
- **Static IP:** Stable URL, but fewer available hosts and potentially higher cost.
- **Recommendation:** Use Cloudflare tunnel. Update `config.yaml` with new URL on each instance restart. This is acceptable for a single-user app.

### 5. Image resolution
- FLUX Klein 4B supports up to 4 megapixels (dimensions must be multiples of 16).
- Common output: 1024x1024.
- Should uploaded sketches be resized to a fixed size, or should we preserve aspect ratio?
- **Recommendation:** Resize to fit within 1024x1024 (preserving aspect ratio, rounding dimensions to nearest multiple of 16). Let user sketches be any reasonable size on input.

### 6. Output format
- ComfyUI `SaveImage` outputs RGB PNG (no alpha).
- The overlay effect is achieved in the frontend by layering the original transparent sketch PNG over the AI-generated colorized image.
- Do we need the AI output itself to have transparency? Likely no — the sketch overlay approach is cleaner.
- **Recommendation:** AI output as standard RGB PNG. Overlay compositing in frontend only.

### 7. WebSocket vs. polling for progress
- ComfyUI supports both WebSocket (`/ws`) and polling (`/history/{id}`).
- With 4-step inference (~1-2 seconds), real-time progress may not be necessary.
- **Recommendation:** Start with simple polling (every 500ms). Add WebSocket later if the UX feels sluggish.

### 8. Multiple generations / history
- Should the app support generating multiple variations and comparing them?
- MVP: single generation at a time, replace previous result.
- Future: gallery of recent generations, seed display for reproducibility.
- **Recommendation:** MVP = single result. Defer history/gallery.

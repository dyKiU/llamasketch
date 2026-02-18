# Pencil Flux Klein — Project Planning

> Pencil sketch autocomplete using FLUX Klein 4B on Vast.ai

---

## Project Overview

**Goal:** Build a simple webapp that takes pencil sketches and uses FLUX Klein 4B to "color them in" / autocomplete them into full images.

**Key Features:**
- Single user, no auth required
- Local webapp → Vast.ai GPU backend
- Upload or select from 3 preloaded pencil sketches
- AI completes/colorizes the sketch
- Display result as overlay on original

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     LOCAL MACHINE                                │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │     Frontend        │    │          Backend                │ │
│  │   (Vanilla JS)      │───▶│        (FastAPI)                │ │
│  │                     │    │                                 │ │
│  │  - Upload sketch    │    │  - Proxy to Vast.ai             │ │
│  │  - Select preset    │    │  - Handle image conversion      │ │
│  │  - Show overlay     │    │  - Serve static sketches        │ │
│  └─────────────────────┘    └──────────────┬──────────────────┘ │
└────────────────────────────────────────────┼────────────────────┘
                                             │
                                             │ SSH Tunnel / HTTP
                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      VAST.AI GPU SERVER                          │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      ComfyUI                                 │ │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │ │
│  │  │ Load Image  │───▶│ FLUX Klein  │───▶│ Save Image      │  │ │
│  │  │ (sketch)    │    │ 4B img2img  │    │ (result PNG)    │  │ │
│  │  └─────────────┘    └─────────────┘    └─────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  SSH: ssh -p 21151 root@74.48.78.46                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Frontend
| Component | Choice | Reason |
|-----------|--------|--------|
| Framework | Vanilla JS + HTML/CSS | Simple, no build step |
| Styling | Tailwind CDN | Quick prototyping |
| Image handling | Canvas API | Overlay composition |

### Backend
| Component | Choice | Reason |
|-----------|--------|--------|
| Framework | FastAPI (Python) | Async, easy, good for proxying |
| Image processing | Pillow | PNG handling, transparency |
| HTTP client | httpx | Async requests to ComfyUI |

### Vast.ai Server
| Component | Choice | Reason |
|-----------|--------|--------|
| Inference | ComfyUI | Native FLUX support, API mode |
| Model | FLUX Klein 4B | Fast, 8-12GB VRAM quantized |
| Access | SSH tunnel or direct HTTP | Secure connection |

---

## API Design

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve frontend |
| `GET` | `/api/sketches` | List available preset sketches |
| `GET` | `/api/sketches/{id}` | Get specific sketch image |
| `POST` | `/api/generate` | Submit sketch for completion |
| `GET` | `/api/status/{job_id}` | Poll generation status |
| `GET` | `/api/result/{job_id}` | Get completed image |
| `GET` | `/api/health` | Health check (incl. Vast.ai connection) |

### Generate Request
```json
{
  "sketch": "<base64 PNG or preset ID>",
  "prompt": "colorful illustration, detailed",
  "strength": 0.75,
  "steps": 20
}
```

### Generate Response
```json
{
  "job_id": "abc123",
  "status": "queued"
}
```

---

## Data Flow

```
1. User uploads sketch OR selects preset
         │
         ▼
2. Frontend displays sketch in canvas
         │
         ▼
3. User clicks "Generate"
         │
         ▼
4. Frontend sends sketch (base64) to /api/generate
         │
         ▼
5. Backend forwards to ComfyUI API on Vast.ai
         │
         ▼
6. ComfyUI runs FLUX Klein img2img workflow
         │
         ▼
7. Backend polls ComfyUI for completion
         │
         ▼
8. Result image returned to frontend
         │
         ▼
9. Frontend composites result as overlay on original sketch
```

---

## Config File Structure

```yaml
# config.yaml

vastai:
  host: "74.48.78.46"
  ssh_port: 21151
  comfyui_port: 8188
  ssh_key: "~/.ssh/id_ed25519"
  user: "root"

generation:
  default_prompt: "colorful detailed illustration, vibrant colors"
  default_strength: 0.75
  default_steps: 20
  model: "flux-klein-4b"

sketches:
  - id: "house"
    name: "Simple House"
    file: "sketches/house.png"
    default_prompt: "cozy cottage, sunny day, garden"
  
  - id: "cat"
    name: "Cat Outline"  
    file: "sketches/cat.png"
    default_prompt: "fluffy orange cat, cute, detailed fur"
  
  - id: "landscape"
    name: "Mountain Landscape"
    file: "sketches/landscape.png"
    default_prompt: "majestic mountains, sunset, dramatic sky"

server:
  host: "127.0.0.1"
  port: 8000
  debug: true
```

---

## Vast.ai Setup Instructions

### 1. Rent GPU Instance
- RTX 3090 or 4090 (24GB VRAM)
- Ubuntu image with CUDA
- Open ports: 22 (SSH), 8188 (ComfyUI)

### 2. SSH Connection
```bash
ssh -p 21151 -i ~/.ssh/id_ed25519 root@74.48.78.46
```

### 3. Install ComfyUI
```bash
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt
```

### 4. Download FLUX Klein 4B
```bash
cd models/checkpoints
# Download from HuggingFace
huggingface-cli download black-forest-labs/FLUX.2-klein-4B --local-dir .
```

### 5. Start ComfyUI in API Mode
```bash
python main.py --listen 0.0.0.0 --port 8188
```

### 6. SSH Tunnel (if needed)
```bash
# From local machine
ssh -L 8188:localhost:8188 -p 21151 root@74.48.78.46
```

---

## ComfyUI Workflow

### Workflow Structure (img2img)
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Load Image   │────▶│ VAE Encode   │────▶│ KSampler     │
│ (sketch.png) │     │              │     │ denoise=0.75 │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
┌──────────────┐     ┌──────────────┐             │
│ CLIP Text    │────▶│ FLUX Klein   │─────────────┘
│ Encode       │     │ 4B Model     │
└──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐     ┌──────────────┐
                     │ VAE Decode   │────▶│ Save Image   │
                     │              │     │ (result.png) │
                     └──────────────┘     └──────────────┘
```

### Key Parameters
| Parameter | Value | Notes |
|-----------|-------|-------|
| denoise | 0.65-0.85 | Higher = more deviation from sketch |
| steps | 15-25 | Balance speed/quality |
| cfg_scale | 3.5-7.0 | FLUX likes lower CFG |
| sampler | euler | Fast, good for FLUX |

---

## MVP Milestones

### M1: Infrastructure ✅
- [x] Create project structure
- [x] SSH connection to Vast.ai working
- [ ] ComfyUI running on Vast.ai
- [ ] Test FLUX Klein inference manually

### M2: Backend
- [ ] FastAPI skeleton
- [ ] Config loading
- [ ] ComfyUI API client
- [ ] /api/generate endpoint
- [ ] Job status polling

### M3: Frontend
- [ ] Basic HTML/CSS layout
- [ ] Sketch upload/select UI
- [ ] Canvas for display
- [ ] API integration
- [ ] Overlay composition

### M4: Integration
- [ ] End-to-end flow working
- [ ] Error handling
- [ ] Loading states
- [ ] Result download

### M5: Polish
- [ ] Preset sketches finalized
- [ ] UI improvements
- [ ] Documentation
- [ ] Easy start script

---

## File Structure

```
pencil-flux-klein/
├── planning.md              # This file
├── config.yaml              # Configuration
├── requirements.txt         # Python dependencies
│
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── config.py            # Config loader
│   ├── comfyui.py           # ComfyUI API client
│   └── routes/
│       ├── __init__.py
│       ├── generate.py      # Generation endpoints
│       └── sketches.py      # Sketch endpoints
│
├── frontend/
│   ├── index.html           # Main page
│   ├── style.css            # Styles
│   └── app.js               # Frontend logic
│
├── sketches/                # Preset pencil sketches
│   ├── house.png
│   ├── cat.png
│   └── landscape.png
│
├── workflows/               # ComfyUI workflow JSONs
│   └── img2img_flux.json
│
└── scripts/
    ├── setup_vastai.sh      # Vast.ai setup script
    └── start.sh             # Local dev start script
```

---

## Open Questions

### Architecture
- [ ] SSH tunnel vs direct HTTP to Vast.ai?
- [ ] WebSocket for real-time progress vs polling?

### Model / Generation
- [ ] Optimal denoise strength for sketch completion?
- [ ] Should we use ControlNet for better sketch adherence?
- [ ] FLUX Klein 4B vs 9B — quality difference worth the VRAM?

### Image Processing
- [ ] How to handle non-square sketches?
- [ ] Transparent PNG output or solid background?
- [ ] Overlay opacity — fixed or user-adjustable?

### Infrastructure
- [ ] Persistent Vast.ai instance or spin up on demand?
- [ ] Cost estimate for typical usage?
- [ ] Fallback if Vast.ai unavailable?

---

## Existing Connection

```bash
# Vast.ai GPU box
ssh -p 21151 -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@74.48.78.46
```

---

*Created: 2026-02-18*

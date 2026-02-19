# Pencil Flux Klein - Project Notes

## Vast.ai Instance

- **SSH**: `ssh -p 21151 -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@74.48.78.46`
- **GPU**: NVIDIA GeForce RTX 4090 (24 GB VRAM)
- **ComfyUI**: Internal port `18188` (NOT 8188 — that goes through an auth proxy)
- **ComfyUI version**: Updated to v0.14.1 (latest master as of 2026-02-19)
- **PyTorch**: 2.9.1+cu128, CUDA 12.8

## Issues Encountered

### 1. SSH Authentication

**Problem**: `Permission denied (publickey)` when trying to SCP files to the instance.

**Root cause**: The Vast.ai instance doesn't automatically add your SSH key to `~/.ssh/authorized_keys`.

**Fix**: Manually add your public key via the Vast.ai Jupyter terminal:
```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-ed25519 AAAA... your-key" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 2. ComfyUI Port (401 Unauthorized)

**Problem**: All API calls to `http://127.0.0.1:8188/` returned 401 Unauthorized.

**Root cause**: Vast.ai's ComfyUI template runs ComfyUI on internal port **18188**. Port 8188 goes through Caddy reverse proxy with authentication.

**Fix**: Use `http://127.0.0.1:18188` for all internal API calls.

### 3. Setup Script cp Error

**Problem**: `scripts/setup_vastai.sh` Step 6 failed with `cp: '/workspace/workflow_template.json' and '/workspace/workflow_template.json' are the same file`.

**Root cause**: Script tried to copy a file onto itself when run from `/workspace/`.

**Fix**: Added `realpath` comparison to skip copy when source == destination.

### 4. Black Output / NaN in VAE Decode (ONGOING)

**Problem**: All inference produces completely black output images (every pixel = (0,0,0)).

**Debugging timeline**:

| Attempt | Configuration | Result |
|---------|--------------|--------|
| KSampler + FP8 model + default VAE | Black output, `RuntimeWarning: invalid value encountered in cast` |
| KSampler + `weight_dtype: "fp8_e4m3fn"` | Black output |
| KSampler + `weight_dtype: "default"` | Black output |
| `--fp32-vae` flag | **CUDA crash**: `illegal memory access` in `upsample_nearest2d` |
| `--bf16-vae` flag | Black output (6/262144 non-black pixels) |
| `--cpu-vae` flag (FP32 on CPU) | Black output |
| `VAEDecodeTiled` | Black output (no crash) |
| BF16 model from Comfy-Org + `fp8_e4m3fn` | Black output |
| BF16 model from Comfy-Org + `default` | Black output |
| Official workflow: `SamplerCustomAdvanced` + `CFGGuider` + `Flux2Scheduler` | Black output |
| Updated ComfyUI v0.13.0 → v0.14.1 | Black output |

**Key findings**:
- VAE roundtrip (encode → decode without sampling) also produces black — initially seemed like VAE issue
- BUT: `--cpu-vae` (FP32 on CPU) also produces black, ruling out VAE precision
- The sampler completes quickly (4 steps, ~1s) but latent output appears to be all NaN
- `--fp32-vae` causes CUDA illegal memory access crash (separate from the NaN issue)
- ComfyUI help text literally says `--fp16-vae` "might cause black images"
- FLUX.2 uses 128-channel latent space (vs 16 for FLUX.1) — VAEs are NOT interchangeable

**Warning**: `"You need pytorch with cu130 or higher to use optimized CUDA operations"` — PyTorch is cu128, ComfyUI's `comfy_kitchen` FP8 kernels are disabled. Unclear if this affects BF16 model inference.

**Current hypothesis**: Either the sampling itself produces NaN (which would mean the model forward pass has issues on this GPU/driver/PyTorch combo), or there's a subtle bug in how ComfyUI handles FLUX.2 Klein on cu128.

**Next step**: Running direct Python inference test (bypassing ComfyUI node system) to check if model forward pass produces valid latents.

### 5. ComfyUI Process Management

**Problem**: Setting `COMFYUI_ARGS` required understanding the Vast.ai supervisor chain.

**How it works**:
1. Supervisor manages ComfyUI via `/etc/supervisor/conf.d/comfyui.conf`
2. The conf runs `/opt/supervisor-scripts/comfyui.sh`
3. That script sources `/opt/supervisor-scripts/utils/environment.sh`
4. Which sources `/etc/environment` (where `COMFYUI_ARGS` is set)
5. Default: `COMFYUI_ARGS="--disable-auto-launch --disable-xformers --port 18188 --enable-cors-header"`

**To change ComfyUI flags**: Edit `COMFYUI_ARGS` in `/etc/environment`, then `supervisorctl restart comfyui`.

**Warning**: If you also set `COMFYUI_ARGS` in the supervisor conf's `environment=` line, the last-sourced value wins (usually `/etc/environment`).

### 6. FLUX.2 Klein Correct Workflow (NOT KSampler)

**Problem**: Original workflow used `KSampler` — this is WRONG for FLUX.2 models.

**Correct workflow** (from official ComfyUI templates):
- `SamplerCustomAdvanced` (not `KSampler`)
- `CFGGuider` (cfg=1.0 for distilled, cfg=5.0 for base)
- `Flux2Scheduler` (not `simple` or `normal` scheduler)
- `RandomNoise` (separate noise node)
- `KSamplerSelect` (sampler_name="euler")
- `EmptyFlux2LatentImage` (not `EmptyLatentImage`)
- `ConditioningZeroOut` on negative (for distilled model)

**Model files**:
- Distilled: `flux-2-klein-4b.safetensors` (4 steps, cfg=1.0)
- Base: `flux-2-klein-base-4b.safetensors` (20 steps, cfg=5.0)
- Both from [Comfy-Org/flux2-klein-4B](https://huggingface.co/Comfy-Org/flux2-klein-4B) (BF16, ~7.75 GB)
- FP8 version from black-forest-labs also available (~4 GB) but was producing NaN

## Model Files on Instance

```
/workspace/ComfyUI/models/
  diffusion_models/
    flux-2-klein-4b-fp8.safetensors  (3.8 GB, FP8 from black-forest-labs)
    flux-2-klein-4b.safetensors      (7.3 GB, BF16 from Comfy-Org)
  text_encoders/
    qwen_3_4b.safetensors            (7.5 GB)
  vae/
    flux2-vae.safetensors            (321 MB)
    ae.safetensors                   (335 MB, FLUX.1 VAE - INCOMPATIBLE)
```

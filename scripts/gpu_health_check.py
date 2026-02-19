#!/usr/bin/env python3
"""GPU health check — run this FIRST on any new Vast.ai instance.

Detects bad VRAM and CUDA kernel execution failures by testing basic
tensor operations at various sizes. A healthy GPU should pass all tests
with zero bad elements.

Usage: python3 gpu_health_check.py
Exit code: 0 = healthy, 1 = defective
"""

import sys

try:
    import torch
except ImportError:
    print("ERROR: PyTorch not found. Activate venv first: source /venv/main/bin/activate")
    sys.exit(1)


def test_multiply(sizes):
    """Test element-wise multiplication at various tensor sizes."""
    print("=== Element-wise Multiplication ===")
    total_bad = 0
    for size in sizes:
        x = torch.full((size,), 2.0, device="cuda", dtype=torch.float32)
        y = torch.full((size,), 3.0, device="cuda", dtype=torch.float32)
        result = x * y
        torch.cuda.synchronize()
        r = result.cpu()
        bad = (r != 6.0).sum().item()
        total_bad += bad
        status = "OK" if bad == 0 else "FAIL"
        print(f"  [{status}] size={size:>7d}: bad={bad} range=[{r.min().item():.1f}, {r.max().item():.1f}]")
    return total_bad


def test_matmul(sizes):
    """Test matrix multiplication at various sizes."""
    print("=== Matrix Multiplication ===")
    total_bad = 0
    for n in sizes:
        a = torch.ones(n, n, device="cuda", dtype=torch.float32)
        b = torch.ones(n, n, device="cuda", dtype=torch.float32) * 2.0
        c = torch.matmul(a, b)
        torch.cuda.synchronize()
        expected = 2.0 * n
        c_cpu = c.cpu()
        bad = (c_cpu != expected).sum().item()
        total_bad += bad
        status = "OK" if bad == 0 else "FAIL"
        print(f"  [{status}] n={n:>4d}: bad={bad}/{n*n} expected={expected:.0f} range=[{c_cpu.min().item():.1f}, {c_cpu.max().item():.1f}]")
    return total_bad


def test_memory_isolation():
    """Test that tensor memory doesn't bleed between allocations."""
    print("=== Memory Isolation ===")
    total_bad = 0
    for size in [50000, 128000]:
        # Create tensor with sentinel, then free it
        sentinel = torch.full((size,), -999.0, device="cuda", dtype=torch.float32)
        del sentinel
        torch.cuda.synchronize()
        # New tensors should not contain -999.0
        x = torch.full((size,), 2.0, device="cuda", dtype=torch.float32)
        y = torch.full((size,), 3.0, device="cuda", dtype=torch.float32)
        result = x * y
        torch.cuda.synchronize()
        r = result.cpu()
        has_sentinel = ((r == -2997.0) | (r == -999.0)).sum().item()
        bad = (r != 6.0).sum().item()
        total_bad += bad
        status = "OK" if bad == 0 else "FAIL"
        print(f"  [{status}] size={size:>7d}: bad={bad} sentinel_leak={has_sentinel}")
    return total_bad


def test_bf16_operations():
    """Test bfloat16 operations (used by FLUX models)."""
    print("=== BFloat16 Operations ===")
    total_bad = 0
    for size in [1000, 50000, 128000]:
        x = torch.ones(size, device="cuda", dtype=torch.bfloat16)
        y = torch.ones(size, device="cuda", dtype=torch.bfloat16) * 3.0
        result = x * y
        torch.cuda.synchronize()
        r = result.cpu().float()
        bad = ((r - 3.0).abs() > 0.1).sum().item()
        total_bad += bad
        status = "OK" if bad == 0 else "FAIL"
        print(f"  [{status}] size={size:>7d}: bad={bad} range=[{r.min().item():.2f}, {r.max().item():.2f}]")
    return total_bad


def main():
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA: {torch.version.cuda}")
    if not torch.cuda.is_available():
        print("ERROR: CUDA not available")
        sys.exit(1)
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print()

    total_bad = 0
    total_bad += test_multiply([100, 1000, 10000, 50000, 128000])
    print()
    total_bad += test_matmul([64, 256, 1024])
    print()
    total_bad += test_memory_isolation()
    print()
    total_bad += test_bf16_operations()
    print()

    if total_bad == 0:
        print("RESULT: GPU is HEALTHY — all tests passed")
        sys.exit(0)
    else:
        print(f"RESULT: GPU is DEFECTIVE — {total_bad} bad elements detected")
        print("This GPU has bad VRAM or a driver issue. Rent a different instance.")
        sys.exit(1)


if __name__ == "__main__":
    main()

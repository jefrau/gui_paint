"""Probe what the GPU API allows in background mode.

M1 needs to know whether any drawing code can run headless before the Canvas
layer is designed. This check records capabilities; it fails only if the probe
itself cannot run.

Reading the report: a failure may mean the API is unavailable, or only that the
call shape used here is wrong for this version. Treat the import, init and
shader entries as the load-bearing ones.
"""

import json
import sys

import bpy

report = {"blender": bpy.app.version_string, "python": sys.version.split()[0]}


def record(key, fn):
    """Store fn's result, or the exception that stopped it."""
    try:
        report[key] = fn()
    except Exception as exc:  # the exception is the finding
        report[key] = f"{type(exc).__name__}: {exc}"


def make_batch():
    """Build a minimal triangle batch, near the shape Canvas.rect will need."""
    fmt = gpu.types.GPUVertFormat()
    fmt.attr_add(id="pos", comp_type="F32", len=2, fetch_mode="FLOAT")
    buf = gpu.types.GPUVertBuf(len=3, format=fmt)
    buf.attr_fill(id="pos", data=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)])
    gpu.types.GPUBatch(type="TRIS", buf=buf)
    return "ok"


try:
    import gpu
except Exception as exc:
    report["import_gpu"] = f"{type(exc).__name__}: {exc}"
else:
    report["import_gpu"] = "ok"
    report["has_init"] = hasattr(gpu, "init")
    if report["has_init"]:
        record("init", lambda: gpu.init() or "ok")
    for name in ("UNIFORM_COLOR", "POINT_UNIFORM_COLOR", "SMOOTH_COLOR"):
        record(f"shader.{name}", lambda n=name: type(gpu.shader.from_builtin(n)).__name__)
    record("batch", make_batch)

print("GPU_PROBE " + json.dumps(report, sort_keys=True))

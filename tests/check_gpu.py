"""Probe what the GPU API allows in background mode, and pin the finding.

The M1 design rests on one measured difference: 5.2 exposes `gpu.init` and can build
shaders and batches from a background process, while 4.2 exposes no `gpu.init` and
refuses every GPU call.

This is the check that owns the import assertion: a broken `gpu` module fails here.
Where `gpu.init` exists the drawing path is asserted to really work, so a regression
fails the suite; where it does not, the limitation is recorded as a skip instead of
being printed as a pass.
"""

import json
import sys

import bpy

from checkkit import banner, check, finish, skip

report = {"blender": bpy.app.version_string, "python": sys.version.split()[0]}


def record(key, fn):
    """Store fn's result, or the exception that stopped it."""
    try:
        report[key] = fn()
    except Exception as exc:  # the exception is the finding
        report[key] = f"{type(exc).__name__}: {exc}"


banner()

try:
    import gpu
except Exception as exc:
    check("gpu imports", False, f"{type(exc).__name__}: {exc}")
else:
    check("gpu imports", True)

    if not hasattr(gpu, "init"):
        skip("this build exposes no gpu.init, so the GPU is unreachable in background")
    else:
        gpu.init()

        def make_batch():
            """Build the six-vertex triangle list Canvas.rect draws."""
            fmt = gpu.types.GPUVertFormat()
            fmt.attr_add(id="pos", comp_type="F32", len=2, fetch_mode="FLOAT")
            buf = gpu.types.GPUVertBuf(len=6, format=fmt)
            buf.attr_fill(id="pos", data=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)] * 2)
            gpu.types.GPUBatch(type="TRIS", buf=buf)
            return "ok"

        record("shader.UNIFORM_COLOR", lambda: type(gpu.shader.from_builtin("UNIFORM_COLOR")).__name__)
        record("batch", make_batch)
        check(
            "the draw path builds a uniform-colour shader",
            report.get("shader.UNIFORM_COLOR") == "GPUShader",
            str(report.get("shader.UNIFORM_COLOR")),
        )
        check(
            "the draw path builds a vertex batch",
            report.get("batch") == "ok",
            str(report.get("batch")),
        )

print("GPU_PROBE " + json.dumps(report, sort_keys=True))
finish("gpu")
